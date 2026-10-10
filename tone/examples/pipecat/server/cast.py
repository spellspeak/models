"""The characters: their prompts, and `CharacterWorker`, the worker that speaks as one.

Each character is a worker of its own, with its own LLM and its own TTS (its voice, sent to its
own transport destination, so it plays on its own audio track in the room):

    bridge in → LLM → Script → Mood → TTS → Stamp → bridge out

A line arrives as a `speak` job from the room: the character's view of the whole conversation
(with a note on how they feel about everyone), a take id, and the audio tag for their mood, which
`Mood` puts in front of the line for Eleven v4 to perform ("[angry] Get out."). The worker
writes the line (sending it back as a job update as soon as it's written, so the room can plan
what follows while it's still being voiced), voices it, and answers the job once the TTS is done. Every frame it sends carries the take id, so the room can
hold a line until its turn and drop anything from a line it has abandoned. Cancelling the job
interrupts the worker.

Characters take no frames from the bus: with several of them active at once, each would echo
the others' frames back onto it. Their lines come as jobs, and they only ever send.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from loguru import logger
from pipecat.bus import BusJobCancelMessage, BusJobRequestMessage
from pipecat.bus.messages import BusFrameMessage, BusMessage
from pipecat.frames.frames import (
    Frame,
    InterruptionFrame,
    LLMContextFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    TTSStoppedFrame,
)
from pipecat.pipeline.job_context import JobStatus
from pipecat.pipeline.job_decorator import job
from pipecat.pipeline.pipeline import Pipeline
from pipecat.processors.aggregators.llm_context import LLMContext, LLMContextMessage
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.llm_service import LLMService
from pipecat.services.tts_service import TTSService
from pipecat.workers.llm import LLMWorker

from config import SPEAK_JOB, VOICE_TIMEOUT_S, WRITE_TIMEOUT_S, Character
from room import SILENT, could_be_silent, is_silent

PROMPTS = Path(__file__).resolve().parent / "prompts"
TAKE = "take"  # the frame metadata key: which line a frame belongs to


def prompt(me: Character, cast: Sequence[Character]) -> str:
    """`me`'s system prompt: `prompts/character.md`, with `prompts/<id>.md` as their persona. With
    others in the garage, they're listed, and `prompts/group.md` says how to share the floor."""
    persona_file = PROMPTS / f"{me.id}.md"
    persona = persona_file.read_text().strip() if persona_file.exists() else ""
    others = [c for c in cast if c.id != me.id]
    values = {
        "name": me.name,
        "role": me.role.lower(),
        "tagline": me.tagline,
        "persona": persona,
        "looks": me.looks(),
        "topics": me.topics,
        "company": (
            "You're there with the others and a person who has just walked in, all talking out "
            "loud. Everyone hears everything that is said."
            if others
            else "Nobody else is here tonight: it's just you and a person who has just walked in."
        ),
        "others": "The others here:\n" + "\n".join(f"- {c.brief()}" for c in others)
        if others
        else "",
        "example": others[0].name if others else "Name",
    }
    text = re.sub(r"\n{3,}", "\n\n", fill((PROMPTS / "character.md").read_text().strip(), values))
    if others:
        text += "\n\n" + fill((PROMPTS / "group.md").read_text().strip(), values)
    return text


def fill(template: str, values: dict[str, str]) -> str:
    return re.sub(r"\{\{\s*(\w+)\s*\}\}", lambda m: values[m.group(1)], template)


def take_of(frame: Frame) -> int | None:
    """The line a character's frame belongs to (None: no line, or one abandoned)."""
    return frame.metadata.get(TAKE)


class Script(FrameProcessor):
    """Between the LLM and the TTS: the line as it's written, reported once it's whole.

    A character may choose to stay quiet (a question to everyone that's someone else's to answer)
    by writing only `SILENT`. The first words of every line are held back until they can't be
    that, so it never reaches the TTS. Anything in square brackets (a handoff, `[to Bruno]`) is
    for the room, not to be said: it's kept out of what the TTS hears, and reported with the line.

    Each response belongs to the take it started for: the end of a response cut short (an
    abandoned line, ending after the next line's job has begun) mustn't be taken for the new
    line, written as nothing.
    """

    def __init__(self, worker: CharacterWorker, name: str) -> None:
        super().__init__(name=f"{name}::Script")
        self._worker = worker
        self._take: int | None = None  # the take the response being written is for
        self._text: list[str] = []
        self._held: list[Frame] | None = None  # the line so far, while it could be SILENT
        self._bracketed = False  # inside a [tag]: not spoken

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMFullResponseStartFrame):
            self._take, self._text, self._held = self._worker.take, [], []
            self._bracketed = False
        elif isinstance(frame, LLMTextFrame):
            self._text.append(frame.text)
            if self._held is not None:
                self._held.append(frame)
                if not could_be_silent("".join(self._text)):
                    await self._release()
                return
            if not self._spoken(frame):
                return
        elif isinstance(frame, LLMFullResponseEndFrame):
            text, take, self._take = "".join(self._text), self._take, None
            if take is None or take != self._worker.take:
                self._held = None  # the end of a response cut short: not this line's
            elif is_silent(text):
                self._held = None  # never voiced
                self._worker.written(SILENT)
            else:
                await self._release()
                self._worker.written(text)
        elif isinstance(frame, InterruptionFrame):
            self._take, self._text, self._held = None, [], None
            self._bracketed = False
        await self.push_frame(frame, direction)

    async def _release(self) -> None:
        held, self._held = self._held or [], None
        for frame in held:
            if not isinstance(frame, LLMTextFrame) or self._spoken(frame):
                await self.push_frame(frame)

    def _spoken(self, frame: LLMTextFrame) -> bool:
        """Keep the [tags] out of a piece of the line; False if nothing in it is to be said."""
        kept = []
        for ch in frame.text:
            if ch == "[":
                self._bracketed = True
            elif ch == "]" and self._bracketed:
                self._bracketed = False
            elif not self._bracketed:
                kept.append(ch)
        frame.text = "".join(kept)
        return bool(frame.text)


class Mood(FrameProcessor):
    """Between the Script and the TTS: the line opens with its audio tag ("[angry] ", "[happy] "),
    which Eleven v4 performs rather than says. The Script has already taken any brackets the LLM
    wrote out of what's voiced, so the only tag the TTS sees is this one."""

    def __init__(self, worker: CharacterWorker, name: str) -> None:
        super().__init__(name=f"{name}::Mood")
        self._worker = worker
        self._opening = False  # the line's first words are still to come

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMFullResponseStartFrame):
            self._opening = True
        elif isinstance(frame, InterruptionFrame):
            self._opening = False
        elif isinstance(frame, LLMTextFrame) and self._opening and frame.text.strip():
            self._opening = False
            if self._worker.voice_tag:
                frame.text = f"{self._worker.voice_tag} {frame.text.lstrip()}"
        await self.push_frame(frame, direction)


class Stamp(FrameProcessor):
    """After the TTS: each frame is stamped with the line it belongs to. The line's runs of
    TTS audio are counted (each ends with a TTSStoppedFrame), and the first run to end after the
    whole line was written means it's voiced."""

    def __init__(self, worker: CharacterWorker, name: str) -> None:
        super().__init__(name=f"{name}::Stamp")
        self._worker = worker

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        frame.metadata[TAKE] = self._worker.take
        await self.push_frame(frame, direction)
        if isinstance(frame, TTSStoppedFrame) and frame.metadata[TAKE] is not None:
            self._worker.stopped()


class CharacterWorker(LLMWorker):
    """Speaks as one character: one line per `speak` job, one job at a time."""

    def __init__(self, character: Character, llm: LLMService[Any], tts: TTSService) -> None:
        self.character = character
        self.take: int | None = None  # the line being written and voiced
        self.voice_tag = ""  # the audio tag it opens with
        self._written: asyncio.Future[str] | None = None
        self._voiced = asyncio.Event()
        self._stops = 0  # runs of TTS audio the line has had, each ending in a TTSStoppedFrame
        self._cancelled_early: set[str] = set()  # jobs cancelled before their request arrived
        name = character.id
        pipeline = Pipeline([llm, Script(self, name), Mood(self, name), tts, Stamp(self, name)])
        super().__init__(name, llm=llm, pipeline=pipeline, bridged=(), active=True)

    def accepts_bus_message(self, message: BusMessage) -> bool:
        return not isinstance(message, BusFrameMessage) and super().accepts_bus_message(message)

    async def on_bus_message(self, message: BusMessage) -> None:
        # A cancel travels ahead of data on the bus, so it can overtake its own request: one
        # for a job not seen yet is remembered, and that job is skipped when it comes.
        if (
            isinstance(message, BusJobCancelMessage)
            and message.target == self.name
            and message.job_id not in self.active_jobs
        ):
            self._cancelled_early.add(message.job_id)
        await super().on_bus_message(message)

    @job(name=SPEAK_JOB, sequential=True)
    async def speak(self, message: BusJobRequestMessage) -> None:
        if message.job_id in self._cancelled_early:
            self._cancelled_early.discard(message.job_id)
            await self.send_job_response(message.job_id, status=JobStatus.CANCELLED)
            return
        payload = message.payload or {}
        messages = cast(list[LLMContextMessage], payload["messages"])
        self.take = payload["take"]
        self.voice_tag = str(payload.get("tag") or "")
        self._written = asyncio.get_running_loop().create_future()
        self._voiced.clear()
        self._stops = 0
        name = self.character.name
        tag = self.voice_tag or "no tag"
        logger.debug(f"{name}: take {self.take} ({len(messages)} messages, {tag})")
        try:
            await self.queue_frame(LLMContextFrame(context=LLMContext(messages=messages)))
            try:
                text = await asyncio.wait_for(asyncio.shield(self._written), WRITE_TIMEOUT_S)
            except TimeoutError:
                logger.warning(f"{name}: nothing written in {WRITE_TIMEOUT_S} s")
                await self.queue_frame(InterruptionFrame())
                text = ""
            if message.job_id not in self.active_jobs:
                return  # the room has gone (the session ended)
            await self.send_job_update(message.job_id, {"text": text})
            if text.strip() and not is_silent(text):
                try:
                    await asyncio.wait_for(self._voiced.wait(), VOICE_TIMEOUT_S)
                except TimeoutError:
                    logger.warning(f"{name}: the TTS never said it was done (take {self.take})")
            if message.job_id in self.active_jobs:
                await self.send_job_response(message.job_id, {"text": text, "stops": self._stops})
        except asyncio.CancelledError:
            # The room abandoned the line. Stop the LLM and the TTS now, before this job lets
            # the next one start: an interruption sent any later would cut that one instead.
            # Anything still on its way out carries no take, so the room drops it.
            self.take = None
            await self.queue_frame(InterruptionFrame())
            logger.debug(f"{name}: line abandoned")
            raise
        finally:
            self.take = None
            self._written = None

    def written(self, text: str) -> None:
        if self._written is not None and not self._written.done():
            self._written.set_result(text)

    def stopped(self) -> None:
        """A run of the line's TTS audio has ended; the first after it was all written means
        it's voiced."""
        self._stops += 1
        if self._written is not None and self._written.done():
            self._voiced.set()
