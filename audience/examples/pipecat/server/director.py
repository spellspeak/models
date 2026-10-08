"""`Director`: who answers each user turn, and the processors that let it hear and steer.

The room worker's pipeline, and where the director sits in it:

    transport → STT → Hearing → user aggregator → Router → CastBridge → TTS → transport → Playback
                                                                               → assistant aggregator

- `Hearing` passes the user's words, partial and final, to the director as they are heard. Audience
  reads them as they come (a few ms each), so the client can watch the reading change mid-sentence.
- `Router` takes each finished user turn (the aggregator's `LLMContextFrame`) out of the stream. At
  the start of the turn's answer, the director asks Audience who it was for and hands the turn to
  that agent (or to everyone, one after the other) by activating their worker with their view of
  the conversation.
- `CastBridge` is the bus bridge: the agents' lines come back through it, and it switches the TTS to
  the voice of whoever is speaking, in-band, just before their line.
- `Playback` watches the bot start and stop speaking: the client is told whose voice is playing,
  and when several agents answer, each waits for the one before to finish playing.
- The assistant aggregator's `on_assistant_turn_stopped` tells the director what was actually said
  (cut short if interrupted), and the next agent in line, if any, answers.

The agents never talk to each other: only the user's turns are routed.

Everything goes to the client as RTVI server messages: `cast`, `audience` (each reading, and for a
whole turn the route it led to), `turn` (who has the floor and why), `speaker` (whose voice is
playing) and `line` (the transcript).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from loguru import logger
from pipecat.bus import BusBridgeProcessor
from pipecat.bus.messages import BusFrameMessage, BusMessage
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    Frame,
    InterimTranscriptionFrame,
    LLMContextFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    TranscriptionFrame,
    TTSUpdateSettingsFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.pipeline.worker import PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.deepgram.tts import DeepgramTTSService

from audience import (
    NOTE_WELCOME,
    USER,
    Audience,
    Cue,
    Line,
    Reading,
    Route,
    Transcript,
    normalize,
    plan_route,
)
from cast import TurnArgs, looks
from config import HANDOVER_WAIT_S, Agent

LLM_LINE_FRAMES = (LLMFullResponseStartFrame, LLMTextFrame, LLMFullResponseEndFrame)


def user_text(message: Any) -> str:
    """What the user said in one of the aggregator's context messages ("" for anything else)."""
    if not isinstance(message, dict) or message.get("role") != "user":
        return ""
    content = message.get("content")
    return content if isinstance(content, str) else ""


class Director:
    """Decides who answers, and keeps the one transcript every agent is shown."""

    def __init__(self, cast: list[Agent], audience: Audience) -> None:
        self.agents = cast
        self.cast = {c.id: c for c in cast}
        self.transcript = Transcript(cast)
        self.audience = audience
        self.worker: PipelineWorker | None = None  # the room worker, set once it exists
        self.looking: str | None = None  # the agent the user is looking at (the client says)

        self.active: str | None = None  # the agent whose turn it is (their worker is active)
        self.speaking: str | None = None  # whose line is flowing to the TTS
        self._queue: list[Cue] = []  # turns promised after this one (a group's, the welcome)
        self._generated: dict[str, str] = {}  # each agent's latest line, as written

        self._seen = 0  # messages of the aggregator's context already read
        self._turns = 0  # user turns routed: a preview landing after its turn is dropped
        self._finals: list[str] = []  # the user's words so far this turn
        self._interim = ""
        self._preview_want: str | None = None
        self._preview_task: asyncio.Task | None = None

        self._user_speaking = False
        self._line_started = False  # the current turn's audio has started playing
        self._line_done = asyncio.Event()  # ...and has stopped
        self._tasks: set[asyncio.Task] = set()
        self._handover_task: asyncio.Task | None = None

    # --- Wiring --------------------------------------------------------------------------------

    def spawn(self, coro: Any, name: str) -> asyncio.Task:
        task = asyncio.create_task(coro, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._settled)
        return task

    def _settled(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logger.opt(exception=task.exception()).error(f"Director: {task.get_name()} failed")

    async def emit(self, data: dict[str, Any]) -> None:
        if self.worker is not None and self.worker.rtvi is not None:
            await self.worker.rtvi.send_server_message(data)

    async def close(self) -> None:
        for task in list(self._tasks):
            task.cancel()

    async def send_cast(self) -> None:
        a = self.audience
        await self.emit(
            {
                "type": "cast",
                "agents": [
                    {"id": c.id, "name": c.name, "role": c.role, "looks": looks(c)}
                    for c in self.agents
                ],
                "audience": {"engine": a.engine, "release": a.release, "error": a.error},
            }
        )

    # --- Turns ---------------------------------------------------------------------------------

    async def welcome(self) -> None:
        """Everyone says hello, one after the other."""
        await self.send_cast()
        cues = [Cue(c.id, "welcome", NOTE_WELCOME) for c in self.agents]
        self._queue = cues[1:]
        await self.dispatch(cues[0])

    async def dispatch(self, cue: Cue) -> None:
        """Give `cue.speaker` the floor: activate their worker with their view of the whole
        conversation, and make sure everyone else is quiet."""
        assert self.worker is not None
        messages = self.transcript.view(cue.speaker, cue.note)
        self.active = cue.speaker
        self._line_started = False
        self._line_done = asyncio.Event()
        for other in self.cast:
            if other != cue.speaker:
                await self.worker.deactivate_worker(other)
        await self.worker.activate_worker(cue.speaker, args=TurnArgs(messages=messages))
        name = self.cast[cue.speaker].name
        logger.info(f"Director: {name}'s turn ({cue.reason})")
        await self.emit(
            {
                "type": "turn",
                "speaker": cue.speaker,
                "reason": cue.reason,
                "note": cue.note,
                "at": time.time(),
            }
        )

    async def user_turn(self, context: LLMContext) -> None:
        """A user turn has ended: ask Audience who it was for, record it, and hand them the turn."""
        messages = context.get_messages()
        fresh = messages[self._seen :]
        self._seen = len(messages)
        self._turns += 1
        said = normalize(" ".join(user_text(m) for m in fresh))
        self._finals.clear()
        self._interim = ""
        self._preview_want = None
        # A new turn replaces whatever was still to come (typed turns too: they interrupt without
        # the user ever starting to speak).
        self._queue.clear()
        if self._handover_task is not None and not self._handover_task.done():
            self._handover_task.cancel()
        if not said:  # an interruption with no words: whoever had the floor carries on
            if self.active is not None:
                await self.dispatch(Cue(self.active, "continue"))
            return

        # Read before the line joins the transcript: the request's history is what came before.
        reading = await self.audience.read(said, self.transcript, looking=self.looking, final=True)
        route = plan_route(reading, self.agents, self.transcript.last_user_to())
        line = self.transcript.add(USER, said, to=route.to)
        await self.emit_line(line)
        await self.emit(
            {**reading.to_message(), "looking": self.looking, "route": route.to_message()}
        )
        self.log_reading(reading, route)
        self._queue = route.cues[1:]
        await self.dispatch(route.cues[0])

    async def heard(self, text: str, final: bool) -> None:
        """Words still being spoken: Audience reads them now, for the client to watch."""
        if final:
            self._finals.append(text)
            self._interim = ""
        else:
            self._interim = text
        so_far = normalize(" ".join([*self._finals, self._interim]))
        if not so_far:
            return
        self._preview_want = so_far
        if self._preview_task is None or self._preview_task.done():
            self._preview_task = self.spawn(self._preview(), "preview")

    async def _preview(self) -> None:
        # One read at a time; when it lands, read the latest words if they changed.
        read: str | None = None
        while self._preview_want and self._preview_want != read:
            read, turn = self._preview_want, self._turns
            reading = await self.audience.read(
                read, self.transcript, looking=self.looking, final=False
            )
            if turn != self._turns:  # the turn ended while it was read: the route has it
                return
            await self.emit({**reading.to_message(), "looking": self.looking})

    async def look(self, agent: str | None) -> None:
        """The user looks at an agent (None: at nobody in particular)."""
        self.looking = agent if agent in self.cast else None
        logger.info(f"Director: the user looks at {self.looking or 'nobody'}")

    def line_generated(self, speaker: str, text: str) -> None:
        """An agent's whole line, as written (the TTS's word timings drop some punctuation)."""
        self._generated[speaker] = normalize(text)

    async def line_spoken(self, content: str, interrupted: bool) -> None:
        """An agent's line has ended: record what was said, and hand over to the next in line."""
        speaker = self.speaking
        if speaker is None:
            return
        written = self._generated.pop(speaker, None)
        # A whole line is recorded as written; a line cut short, as far as it was heard.
        text = normalize(content if interrupted or not written else written)
        if not text:
            if interrupted:
                self._queue.clear()
            return
        line = self.transcript.add(speaker, text, to=[USER], interrupted=interrupted)
        await self.emit_line(line)
        if interrupted or self._user_speaking:
            self._queue.clear()
        elif self._queue:
            self._handover_task = self.spawn(self._hand_over(self._queue.pop(0)), "handover")

    async def _hand_over(self, cue: Cue) -> None:
        # The next line waits for this one to finish playing, unless the user takes the floor.
        try:
            await asyncio.wait_for(self._line_done.wait(), HANDOVER_WAIT_S)
        except TimeoutError:
            logger.warning(f"Director: the line didn't finish playing in {HANDOVER_WAIT_S} s")
        if self._user_speaking:
            return
        await self.dispatch(cue)

    # --- What the processors report ------------------------------------------------------------

    async def user_started(self) -> None:
        self._user_speaking = True
        self._queue.clear()
        if self._handover_task is not None and not self._handover_task.done():
            self._handover_task.cancel()

    async def user_stopped(self) -> None:
        self._user_speaking = False

    async def bot_started(self) -> None:
        self._line_started = True
        await self.emit({"type": "speaker", "speaker": self.speaking, "at": time.time()})

    async def bot_stopped(self) -> None:
        if self._line_started:
            self._line_done.set()
        await self.emit({"type": "speaker", "speaker": None, "at": time.time()})

    def line_starting(self, speaker: str) -> None:
        self.speaking = speaker

    # --- Reporting -----------------------------------------------------------------------------

    async def emit_line(self, line: Line) -> None:
        await self.emit(
            {
                "type": "line",
                "speaker": line.speaker,
                "to": line.to,
                "text": line.text,
                "interrupted": line.interrupted,
                "at": time.time(),
            }
        )

    def log_reading(self, reading: Reading, route: Route) -> None:
        a = reading.answer
        if a is None:
            scores = f"failed ({reading.error})"
        else:
            people = ", ".join(f"{k} {v:.2f}" for k, v in a.addressed.items())
            scores = f"{people}; unclear {a.unclear:.2f}, group {a.to_group:.2f}"
        speakers = ", ".join(self.cast[c.speaker].name for c in route.cues)
        logger.info(
            f'Audience ({reading.engine}, {reading.ms:.0f} ms): "{reading.heard}" → {scores} '
            f"→ {route.kind}: {speakers}"
        )

    # --- Processors ----------------------------------------------------------------------------

    def hearing(self) -> Hearing:
        return Hearing(self)

    def router(self) -> Router:
        return Router(self)

    def playback(self) -> Playback:
        return Playback(self)


class Hearing(FrameProcessor):
    """Between the STT and the user aggregator: the user's words as they are heard."""

    def __init__(self, director: Director) -> None:
        super().__init__(name="Hearing")
        self._director = director

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if (
            isinstance(frame, (TranscriptionFrame, InterimTranscriptionFrame))
            and frame.text.strip()
        ):
            await self._director.heard(frame.text, isinstance(frame, TranscriptionFrame))
        await self.push_frame(frame, direction)


class Router(FrameProcessor):
    """After the user aggregator: each finished user turn goes to the director, not the bridge."""

    def __init__(self, director: Director) -> None:
        super().__init__(name="Router")
        self._director = director

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        director = self._director
        if isinstance(frame, LLMContextFrame) and direction == FrameDirection.DOWNSTREAM:
            # Off the frame loop, so the pipeline keeps moving while the turn is routed.
            director.spawn(director.user_turn(frame.context), "route")
            return
        if isinstance(frame, UserStartedSpeakingFrame):
            await director.user_started()
        elif isinstance(frame, UserStoppedSpeakingFrame):
            await director.user_stopped()
        await self.push_frame(frame, direction)


class CastBridge(BusBridgeProcessor):
    """The bus bridge to the agents, which also gives each line its speaker's voice.

    A line starting from an agent (`LLMFullResponseStartFrame` from their worker) switches the TTS
    to their voice first, in the same stream, so the switch lands exactly between two lines. Lines
    from an agent whose turn it no longer is (still in flight after a handover) are dropped. Each
    finished line is passed to the director as written.
    """

    def __init__(self, director: Director, *, voice: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._director = director
        self._voice = voice
        self._text: dict[str, list[str]] = {}

    async def on_bus_message(self, message: BusMessage) -> None:
        director = self._director
        if isinstance(message, BusFrameMessage) and message.source in director.cast:
            frame, speaker = message.frame, message.source
            if isinstance(frame, LLM_LINE_FRAMES) and speaker != director.active:
                return
            if isinstance(frame, LLMFullResponseStartFrame):
                director.line_starting(speaker)
                self._text[speaker] = []
                voice = director.cast[speaker].voice
                if voice != self._voice:
                    self._voice = voice
                    settings = DeepgramTTSService.Settings(voice=voice)
                    await self.push_frame(TTSUpdateSettingsFrame(delta=settings))
            elif isinstance(frame, LLMTextFrame):
                self._text.setdefault(speaker, []).append(frame.text)
            elif isinstance(frame, LLMFullResponseEndFrame):
                director.line_generated(speaker, "".join(self._text.pop(speaker, [])))
        await super().on_bus_message(message)


class Playback(FrameProcessor):
    """After the output transport: when the bot's audio starts and stops playing."""

    def __init__(self, director: Director) -> None:
        super().__init__(name="Playback")
        self._director = director

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, BotStartedSpeakingFrame):
            await self._director.bot_started()
        elif isinstance(frame, BotStoppedSpeakingFrame):
            await self._director.bot_stopped()
        await self.push_frame(frame, direction)
