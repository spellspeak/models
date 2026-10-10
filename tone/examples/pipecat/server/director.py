"""`Director`: who speaks next in the room, how everyone feels about it, and the processors that
let it hear and steer.

The room worker's pipeline:

    transport.input → Flux → Hearing → user aggregator → Router → CastBridge → FloorGate
                    → transport.output → FloorEar

- `Hearing` passes the user's words, partial and final, to the director as they are heard, and
  Audience reads them as they come (a few ms each), so the client can watch the reading change
  mid-sentence. It also passes on when the user's voice starts and stops (the VAD), so that no
  line starts over them.
- `Router` takes each finished user turn (the aggregator's `LLMContextFrame`) out of the stream:
  the director asks Audience who it was for, and plays out the plan (`audience.plan`).
- `CastBridge`, `FloorGate` and `FloorEar` are the floor (`floor.py`): the characters' voices
  come in over the bus, and each line plays when its turn comes, on its speaker's own track.

Tone reads every line (`tone.py`), and `Feelings` (`feelings.py`) moves how each character feels
about whoever said it, and the face they show. The user's line is read as soon as Audience has said
who it's for, before anyone answers, so the characters answer already feeling it; each character's
line is read as it starts playing, so the room's feelings move as it's heard.

Each line is a *take*: a `speak` job sent to the character's worker (`cast.py`) with their view of
the conversation (and a note on how they feel about everyone), the audio tag for their mood, and a
cue on the floor saying what it waits for. A chorus (everyone at once, or
everyone it might have been for asking "Who, me?") is staggered over a second; answers in turn each
wait for the one before, plus a beat. The worker reports the line as soon as it's written, while
its TTS is still voicing it, and the next in turn is asked for once the line before has started
playing: written and voiced while this one plays, so it comes in a beat after it ends.

The user always has the floor when they take it: speaking (past a couple of words, so a laugh
doesn't count) or typing cancels every take still to come and stops every voice.

Everything goes to the client as RTVI server messages: `cast` (with everyone's feelings at the
start), `audience` (each reading, and for a whole turn its plan), `tone` (each line's reading, and
the feelings and faces it moved), `turn` (a take: who and why), `line` (the transcript, as each
line starts playing, and again if it's cut short or taken back) and `voices` (whose audio is
playing).
"""

from __future__ import annotations

import asyncio
import itertools
import random
import time
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from loguru import logger
from pipecat.frames.frames import (
    Frame,
    InterimTranscriptionFrame,
    LLMContextFrame,
    LLMMessagesAppendFrame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.pipeline.job_context import JobError, JobGroupEvent, JobParams
from pipecat.pipeline.worker import PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from audience import Audience, Plan, Reading, Take, plan
from config import (
    CHORUS_STAGGER_S,
    MERGE_GAP_S,
    MORE_MAX_S,
    SPEAK_JOB,
    SPEAK_TIMEOUT_S,
    TRANSCRIPT_LAG_S,
    TURN_GAP_S,
    Character,
)
from feelings import Feelings, Update
from floor import Floor
from room import NOTE, NOTE_HANDOFF, USER, Line, Transcript, handoff, is_silent, normalize
from tone import Tone, ToneReading


def user_text(message: Any) -> str:
    """What the user said in one of the aggregator's context messages ("" for anything else)."""
    if not isinstance(message, dict) or message.get("role") != "user":
        return ""
    content = message.get("content")
    return content if isinstance(content, str) else ""


@dataclass(eq=False)
class Live:
    """A take: a line asked of a character, from being written to having played."""

    take: int
    plan: Take
    epoch: int
    chorus: int | None = None
    line: Line | None = None  # in the transcript once written
    task: asyncio.Task | None = None
    prev: Live | None = None  # the line it follows, in a run of lines in turn
    heard: asyncio.Event = field(default_factory=asyncio.Event)  # set once it starts playing
    done: asyncio.Event = field(default_factory=asyncio.Event)  # set once it's played, or dropped
    started: bool = False  # its audio has started playing
    toned: bool = False  # Tone has read it

    @property
    def speaker(self) -> str:
        return self.plan.speaker


class Director:
    """Decides who speaks, and keeps the one transcript every character is shown."""

    def __init__(self, cast: Sequence[Character], audience: Audience, tone: Tone) -> None:
        self.cast = {c.id: c for c in cast}
        self.transcript = Transcript(cast)
        self.audience = audience
        self.tone = tone
        self.feelings = Feelings(cast)
        self.floor = Floor(self, list(self.cast))
        self.worker: PipelineWorker | None = None  # the room worker, set once it exists

        self._lives: dict[int, Live] = {}
        self._takes = itertools.count(1)
        self._choruses = itertools.count(1)
        self._users = itertools.count(1)
        self._queue: list[Take] = []  # a plan's takes in turn, each asked once the last is written
        self._epoch = 0  # moves on whenever the user takes the floor: older plans are void

        self._seen = 0  # messages of the aggregator's context already read
        self._turns = 0  # user turns routed: a read-along landing after its turn is dropped
        self._finals: list[str] = []  # the user's words so far this turn
        self._interim = ""
        self._preview_want: str | None = None
        self._preview_task: asyncio.Task | None = None
        self._last_user: Line | None = None  # the user's last turn, and its id for the client...
        self._last_user_id = ""
        self._last_user_end = 0.0  # ...and when its words ended, and it was routed (monotonic)
        self._last_user_at = 0.0
        # The user's voice (VAD): whether they're audible now, and when it last started and
        # stopped. It leads the transcript, and so the turn, by up to a second.
        self._voice = False
        self._voice_began = 0.0
        self._voice_ended = 0.0
        self._voice_starts: deque[float] = deque(maxlen=16)
        self._turn_began = 0.0  # when the user's current (or last) turn started
        self._wake = asyncio.Event()  # the voice changed, or the floor was taken
        self._resume: asyncio.Task | None = None  # lets lines start again after a voice stops
        self._user_speaking = False
        self._tasks: set[asyncio.Task] = set()

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
                "characters": [
                    {"id": c.id, "name": c.name, "role": c.role} for c in self.cast.values()
                ],
                "audience": {"engine": a.engine, "release": a.release, "error": a.error},
                "tone": {"release": self.tone.release},
                "feelings": self.feelings.matrix(),
                "faces": self.feelings.faces(),
            }
        )

    # --- Plans and takes -----------------------------------------------------------------------

    async def play(self, plan: Plan) -> None:
        """Start a plan: its first take now and the rest in turn, or all of them at once."""
        if not plan.takes:
            return
        if plan.together:
            # Spread over CHORUS_STAGGER_S from the first voice, in no particular order.
            chorus = next(self._choruses)
            delays = sorted(random.uniform(0.0, CHORUS_STAGGER_S) for _ in plan.takes)
            delays[0] = 0.0
            random.shuffle(delays)
            for take, delay in zip(plan.takes, delays, strict=True):
                await self.ask(take, after=set(), gap=0.0, delay=delay, chorus=chorus)
            return
        self._queue = list(plan.takes[1:])
        await self.ask(plan.takes[0], after=set())

    async def ask(
        self,
        take: Take,
        *,
        after: set[int],
        gap: float = TURN_GAP_S,
        delay: float = 0.0,
        chorus: int | None = None,
        prev: Live | None = None,
    ) -> Live:
        """Ask a character for a line: written now, played once `after` have finished."""
        assert self.worker is not None
        live = Live(next(self._takes), take, self._epoch, chorus, prev=prev)
        self._lives[live.take] = live
        # They answer as they feel now: told so, and voiced so.
        note = " ".join(n for n in (self.feelings.note(take.speaker), take.note) if n)
        view = self.transcript.view(take.speaker, note)
        tag = self.feelings.voice_tag(take.speaker)
        await self.floor.expect(
            live.take, take.speaker, after=after, gap=gap, delay=delay, chorus=chorus
        )
        live.task = self.spawn(self._speak(live, view, tag), f"take {live.take}")
        name = self.cast[take.speaker].name
        logger.info(f"Director: {name}, take {live.take} ({take.reason}, {tag or 'no tag'})")
        await self.emit(
            {
                "type": "turn",
                "take": live.take,
                "speaker": take.speaker,
                "reason": take.reason,
                "note": take.note,
                "tag": tag,
                "at": time.time(),
            }
        )
        return live

    async def _speak(self, live: Live, view: list[dict[str, str]], tag: str) -> None:
        assert self.worker is not None
        payload: dict[str, Any] = {"take": live.take, "messages": view, "tag": tag}
        params = JobParams(name=SPEAK_JOB, payload=payload, timeout=SPEAK_TIMEOUT_S)
        try:
            async with self.worker.job(live.speaker, params=params) as job:
                async for event in job:
                    if event.type == JobGroupEvent.UPDATE and event.data is not None:
                        await self.written(live, str(event.data.get("text", "")))
        except JobError as error:
            logger.warning(f"Director: take {live.take} failed: {error}")
            await self._unheard(live)
            return
        except asyncio.CancelledError:
            logger.debug(f"Director: take {live.take} cancelled")
            raise
        stops = int(job.response.get("stops", 0))
        logger.debug(f"Director: take {live.take} voiced ({stops} runs)")
        await self.floor.complete(live.take, stops)

    async def written(self, live: Live, text: str) -> None:
        """A take's line is written (it's being voiced, and may be waiting for its turn)."""
        text = normalize(text)
        if live.epoch != self._epoch or live.take not in self._lives:
            return
        if not text or is_silent(text):
            if text:
                logger.info(f"Director: {self.cast[live.speaker].name} stays out of it")
            else:
                logger.warning(f"Director: {live.speaker} wrote nothing (take {live.take})")
            await self._unheard(live)
            return
        text, passed = handoff(text, list(self.cast.values()))
        if not text:  # only a tag: nothing to say, the question goes straight over
            await self._unheard(live)
        else:
            live.line = self.transcript.add(
                live.speaker, text, how=live.plan.how, chorus=live.chorus, to=[USER]
            )
        # Asked alone, a character can pass the question to whoever it's really for ("that's
        # Bruno's department"): they answer next. A line passed on can't be passed again.
        if (
            passed is not None
            and passed != live.speaker
            and live.plan.reason in ("addressed", "fallback")
            and live.epoch == self._epoch
        ):
            name = self.cast[live.speaker].name
            logger.info(f"Director: {name} passes it to {self.cast[passed].name}")
            self._queue.append(Take(passed, "handoff", NOTE_HANDOFF.format(other=name)))
            if live.line is None:
                await self.ask(self._queue.pop(0), after=set())
                return
        if live.line is None:
            return
        if live.started:
            # Its first words were voiced, and started playing, before the rest was written.
            await self.emit_line(f"t{live.take}", live.line)
            await self._tone_take(live)
        self.spawn(self._follow(live), f"follow {live.take}")

    async def _unheard(self, live: Live) -> None:
        """A take that won't be heard (it said nothing, or failed): drop it, and let the rest of
        a group in turn go on without it."""
        epoch = self._epoch
        await self.floor.drop(live.take)
        if live.epoch != epoch or live.chorus is not None:
            return
        if self._queue:
            after = {live.prev.take} if live.prev is not None else set()
            await self.ask(self._queue.pop(0), after=after, prev=live.prev)

    async def _follow(self, live: Live) -> None:
        """The next in turn, if any, is asked for once the line before this one has started
        playing: so the room is at most two lines ahead of what's being heard (one waiting its
        turn, one being written), and no more is thrown away when the user cuts in."""
        epoch = self._epoch
        if live.epoch != epoch or live.chorus is not None or not self._queue:
            return
        if live.prev is not None:
            await live.prev.heard.wait()
        if epoch == self._epoch and self._queue:
            await self.ask(self._queue.pop(0), after={live.take}, prev=live)

    # --- What the floor reports ----------------------------------------------------------------

    async def line_started(self, take: int) -> None:
        live = self._lives.get(take)
        if live is not None:
            live.started = True
            live.heard.set()
            if live.line is not None:
                await self.emit_line(f"t{take}", live.line)
                await self._tone_take(live)

    async def line_finished(self, take: int, heard: str | None) -> None:
        live = self._lives.pop(take, None)
        if live is None:
            return
        live.heard.set()
        live.done.set()
        if live.task is not None and not live.task.done():
            live.task.cancel()  # cut short: the character stops writing and voicing it
        if heard is None and not live.started:
            # Finished without a sound (its voice failed): never heard, so it's taken back.
            await self._taken_back(live)
        elif heard is not None:
            # Cut short: recorded as far as it was heard (even if it was never all written).
            if live.line is None and heard:
                live.line = self.transcript.add(live.speaker, heard, how=live.plan.how, to=[USER])
            if live.line is not None and heard:
                live.line.text, live.line.interrupted = heard, True
                await self.emit_line(f"t{take}", live.line)
            else:
                if live.line is not None:
                    self.transcript.remove(live.line)
                await self.emit({"type": "line", "id": f"t{take}", "removed": True})
        elif live.line is None:
            # Played out but never written down (the user had taken the floor by then).
            await self.emit({"type": "line", "id": f"t{take}", "removed": True})

    async def line_dropped(self, take: int) -> None:
        live = self._lives.pop(take, None)
        if live is not None:
            live.done.set()
            await self._taken_back(live)

    async def _taken_back(self, live: Live) -> None:
        """A line never heard: out of the transcript, off the client, its character stopped, and
        whatever was to follow it dropped too."""
        live.heard.set()
        if live.task is not None and not live.task.done():
            live.task.cancel()
        if live.line is not None:
            self.transcript.remove(live.line)
        await self.emit({"type": "line", "id": f"t{live.take}", "removed": True})
        for after in [lv for lv in self._lives.values() if lv.prev is live]:
            await self.floor.drop(after.take)

    async def voices(self, speakers: list[str]) -> None:
        await self.emit({"type": "voices", "speakers": speakers, "at": time.time()})

    # --- The user ------------------------------------------------------------------------------

    async def take_floor(self) -> None:
        """The user takes the floor: every take still to come is void, and every character still
        writing or voicing is stopped. The voices themselves are stopped by the floor, when the
        interruption reaches it."""
        self._epoch += 1
        self._wake.set()
        self._queue.clear()
        for live in list(self._lives.values()):
            if live.task is not None and not live.task.done():
                live.task.cancel()  # cancels the job: the character stops writing and voicing

    async def interrupted(self) -> None:
        """The floor is about to cut every line (the user spoke or typed over the room)."""
        await self.take_floor()

    async def user_started(self) -> None:
        self._turn_began = time.monotonic()
        self._user_speaking = True
        await self.take_floor()

    async def user_stopped(self) -> None:
        self._user_speaking = False

    async def user_turn(self, context: LLMContext) -> None:
        """A user turn has ended (Flux's call): record it, ask Audience who it was for, and play
        the plan. A turn that continues one nobody has answered yet is read as one turn."""
        messages = context.get_messages()
        fresh = messages[self._seen :]
        self._seen = len(messages)
        self._turns += 1
        said = normalize(" ".join(user_text(m) for m in fresh))
        self._finals.clear()
        self._interim = ""
        self._preview_want = None
        # Typed turns interrupt without the user ever starting to speak.
        await self.take_floor()
        epoch = self._epoch
        if self._lives:
            await self.floor.cut_all()
        if not said:
            return

        # When the words of this turn ended: the voice's end, unless the VAD missed them (a short
        # word, quietly said) and its last end is from before this turn: then, now.
        now = time.monotonic()
        ended = self._voice_ended if self._voice_ended >= self._turn_began else now
        last_id = self._last_user_id
        line, line_id, history = self._user_line(said, ended)
        carried_on = line_id == last_id  # the rest of their last turn: only the new words are read
        await self.emit_line(line_id, line)

        reading = await self.audience.read(line.text, history, final=True)
        if epoch != self._epoch:
            return  # another turn has started since (typed, say): it routes itself
        # Nobody talks over the user: if they've gone on, their next words take the floor, and
        # the two are read as one turn.
        if await self._more(epoch, ended):
            return
        if not self._voice:
            await self.floor.resume()  # their words are a turn now: lines may start
        what = plan(reading, line, self.transcript)
        line.to = what.addressed
        await self.emit_line(line_id, line)
        await self.emit({**reading.to_message(), "plan": what.to_message()})
        self.log_reading(reading, what)
        # Tone reads it before anyone answers, so they answer feeling it.
        to = what.addressed[0] if len(what.addressed) == 1 else None
        await self.read_tone(line_id, USER, to, said if carried_on else line.text, history)
        if epoch != self._epoch:
            return
        await self.play(what)

    def _user_line(self, said: str, ended: float) -> tuple[Line, str, list[Line]]:
        """Add what the user said to the transcript, or, if it carries on their last turn (it
        began within MERGE_GAP_S of that one's end, and nothing has been heard since), add it to
        that line. Returns the line, its id for the client, and the conversation before it."""
        lines, last, now = self.transcript.lines, self._last_user, time.monotonic()
        # When they first spoke again after their last turn's words ended (if they have).
        again = next((t for t in self._voice_starts if t > self._last_user_end), None)
        if again is not None:
            went_on = again - self._last_user_end < MERGE_GAP_S
        else:  # no new words since: the transcript of the same words, finalised in two parts
            went_on = now - self._last_user_at < MERGE_GAP_S
        if last is not None and last in lines and went_on:
            after = lines[lines.index(last) + 1 :]
            if all(ln.speaker == NOTE for ln in after):
                last.text = normalize(f"{last.text} {said}")
                self._last_user_end, self._last_user_at = ended, now
                logger.info("Director: the user carried on their last turn")
                return last, self._last_user_id, lines[: lines.index(last)]
        history = list(lines)
        line = self.transcript.add(USER, said)
        self._last_user, self._last_user_id = line, f"u{next(self._users)}"
        self._last_user_end, self._last_user_at = ended, now
        return line, self._last_user_id, history

    async def _more(self, epoch: int, ended: float) -> bool:
        """If the user's voice has started again since their turn's words `ended`, wait until
        those words become a turn (the transcript trails the voice), MORE_MAX_S at most, or
        TRANSCRIPT_LAG_S after the voice stops without one. True if a new turn has taken the
        floor."""
        start = time.monotonic()
        while epoch == self._epoch:
            if self._voice_began <= ended:  # not speaking again
                return False
            lag = self._voice_ended + TRANSCRIPT_LAG_S
            until = start + MORE_MAX_S if self._voice else min(start + MORE_MAX_S, lag)
            left = until - time.monotonic()
            if left <= 0:
                return False
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), left)
            except TimeoutError:
                pass
        return True

    async def voice(self, on: bool) -> None:
        """The VAD heard the user's voice start or stop. Nobody starts a line while they're
        speaking: the floor pauses, and resumes when their words have become a turn (when it's
        routed), or TRANSCRIPT_LAG_S after the voice stops without one (a cough, a laugh)."""
        now = time.monotonic()
        if on and not self._voice:
            self._voice_began = now
            self._voice_starts.append(now)
        elif not on and self._voice:
            self._voice_ended = now
        if on and not self._voice and not self._user_speaking:
            # A new utterance, with no turn open: whatever was heard before it (a laugh that
            # didn't take the floor) is not part of what comes next.
            self._finals.clear()
            self._interim = ""
        self._voice = on
        self._wake.set()
        if self._resume is not None:
            self._resume.cancel()
            self._resume = None
        if on:
            await self.floor.pause()
        else:
            self._resume = self.spawn(self._resume_after(TRANSCRIPT_LAG_S), "resume")

    async def _resume_after(self, delay: float) -> None:
        await asyncio.sleep(delay)
        if not self._voice:
            await self.floor.resume()

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
            history = list(self.transcript.lines)
            reading = await self.audience.read(read, history, final=False)
            if turn != self._turns:  # the turn ended while it was read: the route has it
                return
            await self.emit(reading.to_message())

    async def say(self, text: str) -> None:
        """A line the user typed: in as a finished turn, as a spoken one comes, and routed the same
        way. (RTVI's own send-text interrupts the bot and drains the pipeline first, which holds a
        typed line up by a second or so; the director takes the floor itself.)"""
        if self.worker is not None and text.strip():
            line = {"role": "user", "content": text.strip()[:1000]}
            await self.worker.queue_frame(LLMMessagesAppendFrame(messages=[line], run_llm=True))

    # --- Feelings ------------------------------------------------------------------------------

    async def _tone_take(self, live: Live) -> None:
        """A character's line has started playing: Tone reads it, once."""
        line = live.line
        if live.toned or line is None or line not in self.transcript.lines:
            return
        live.toned = True
        before = self.transcript.lines[: self.transcript.lines.index(line)]
        to = next((t for t in line.to if t != line.speaker), None)
        await self.read_tone(f"t{live.take}", line.speaker, to, line.text, before)

    async def read_tone(
        self, line_id: str, speaker: str, to: str | None, text: str, before: Sequence[Line]
    ) -> None:
        """Tone reads a line said by `speaker` to `to` (None: the room), after the lines `before`;
        everyone's feelings and faces move, and the client is told."""
        if not text:
            return
        prev = next((ln for ln in reversed(before) if ln.speaker != NOTE and ln.text), None)
        previous = self.tone.said(prev.speaker, prev.text) if prev is not None else None
        reading = await self.tone.read(speaker, to, text, previous)
        if reading.tags is None:
            await self.emit({"type": "tone", "line": line_id, "error": reading.error})
            return
        update = self.feelings.on_line(speaker, reading.tags)
        await self.emit(
            {
                "type": "tone",
                "line": line_id,
                "speaker": speaker,
                "to": to,
                "ms": round(reading.ms, 1),
                "emotion": reading.emotion(),
                "acts": reading.acts(),
                "backchannel": reading.tags.backchannel,
                "changes": [c.to_message() for c in update.changes],
                "feelings": self.feelings.matrix(),
                "faces": self.feelings.faces(),
                "at": time.time(),
            }
        )
        self.log_tone(reading, update)

    def log_tone(self, reading: ToneReading, update: Update) -> None:
        tags = reading.tags
        if tags is None:
            return
        who = self.feelings.label(reading.speaker) if reading.speaker != USER else "user"
        acts = ", ".join(
            f"{a.act}/{a.intensity} → {t}" for t, a in tags.acts.items() if a.act != "none"
        )
        moved = ", ".join(f"{c.who}→{c.toward} {c.change:+d} ({c.value})" for c in update.changes)
        faces = ", ".join(f"{w} {m.mood}" for w, m in update.moods.items())
        logger.info(
            f"Tone ({reading.ms:.0f} ms): {who} {tags.emotion}/{tags.emotion_intensity}"
            + (f"; {acts}" if acts else "")
            + (f"; feelings {moved}" if moved else "")
            + (f"; faces {faces}" if faces else "")
        )

    # --- Reporting -----------------------------------------------------------------------------

    async def emit_line(self, id_: str, line: Line) -> None:
        await self.emit(
            {
                "type": "line",
                "id": id_,
                "speaker": line.speaker,
                "to": line.to,
                "text": line.text,
                "how": line.how,
                "interrupted": line.interrupted,
                "at": time.time(),
            }
        )

    def log_reading(self, reading: Reading, what: Plan) -> None:
        a = reading.answer
        if a is None:
            scores = f"failed ({reading.error})"
        else:
            top = sorted(a.addressed.items(), key=lambda kv: -kv[1])
            people = ", ".join(f"{k} {v:.2f}" for k, v in top)
            scores = f"{people}; unclear {a.unclear:.2f}, group {a.to_group:.2f}"
        speakers = ", ".join(self.cast[t.speaker].name for t in what.takes)
        # What was said is only logged at DEBUG: the decisions, not the words.
        logger.info(
            f"Audience ({reading.engine}, {reading.ms:.0f} ms): {scores} → {what.why}: {speakers}"
        )
        logger.debug(f'Audience read: "{reading.heard}"')

    # --- Processors ----------------------------------------------------------------------------

    def hearing(self) -> Hearing:
        return Hearing(self)

    def router(self) -> Router:
        return Router(self)


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
        elif isinstance(frame, (VADUserStartedSpeakingFrame, VADUserStoppedSpeakingFrame)):
            # The user aggregator runs the VAD, and always sends its verdicts back up this
            # way (downstream, only some of the time).
            if direction == FrameDirection.UPSTREAM:
                await self._director.voice(isinstance(frame, VADUserStartedSpeakingFrame))
        await self.push_frame(frame, direction)


class Router(FrameProcessor):
    """After the user aggregator: each finished user turn goes to the director."""

    def __init__(self, director: Director) -> None:
        super().__init__(name="Router")
        self._director = director
        self._route: asyncio.Task | None = None

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        director = self._director
        if isinstance(frame, LLMContextFrame) and direction == FrameDirection.DOWNSTREAM:
            if frame.speculation:
                logger.warning("Router: a speculative turn isn't routed (eager turn-taking is off)")
                return
            # Routed off the frame loop; speech that starts in the meantime cancels the route
            # (the new words make a turn of their own).
            self._route = director.spawn(director.user_turn(frame.context), "route")
            return
        if isinstance(frame, UserStartedSpeakingFrame):
            if self._route is not None and not self._route.done():
                self._route.cancel()
            await director.user_started()
        elif isinstance(frame, UserStoppedSpeakingFrame):
            await director.user_stopped()
        await self.push_frame(frame, direction)
