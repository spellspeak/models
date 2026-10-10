"""SpellSpeak Audience in the room: who the user's line is for, and what the room does about it.

`Audience` asks the model. Its request is the line, a card per character (what the user can see of
them: `characters.json`), the last few lines with who each was for, and what the room knows about
where everyone is: everyone is near the user and in the conversation, and the transcript says who
the user spoke with last and who just asked them something. One read takes a few milliseconds on
the CPU.

`plan` turns the scores into what the room does (the floors are in `config.py`):

- **Everyone** (`to_group`): they all answer. A short line ("hey, all of you!") gets a chorus, all at
  once; a longer one, answers in turn, likeliest first.
- **Unclear** (`unclear`): everyone it might be for asks "Who, me?" at once ("oi, you!").
- **Several, for sure** (two or more at least `SURE_FLOOR`: "Nova and Kai, what's the plan?"):
  they answer in turn. Several fairly likely but none for sure ("oi, you!") is as unclear.
- **One**: the likeliest answers. If even they are below `PERSON_FLOOR`, whoever the user spoke
  with last answers.

With no model (`AUDIENCE_ENGINE=rules`, or no way to load it) the runtime's rules baseline scores
instead: word matching and the rules of evidence, instant, but blind to anything the words don't
spell out.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

import runtimes  # noqa: F401 — both models' runtimes, before their modules
from config import (
    ADDRESSED_FLOOR,
    AUDIENCE_DIR,
    AUDIENCE_FILES,
    AUDIENCE_HF,
    CANDIDATE_FLOOR,
    CHORUS_MAX_WORDS,
    GROUP_FLOOR,
    PERSON_FLOOR,
    PRECISION,
    SURE_FLOOR,
    UNCLEAR_FLOOR,
    Character,
)
from contracts.schemas.addressee import (
    MAX_HISTORY,
    AddresseeAnswer,
    AddresseeRequest,
    HistoryLine,
)
from contracts.schemas.person_card import PersonCard, SpatialFacts
from harness.addressee.rules import rules_answer
from room import (
    NOTE,
    NOTE_CHORUS,
    NOTE_IN_TURN,
    NOTE_SWITCH,
    NOTE_WHO_ME,
    SAID,
    TOGETHER,
    USER,
    Line,
    Transcript,
    names,
    normalize,
)
from runtimes import model_dir

MAX_TEXT = 400  # the longest line the model reads


# --- Readings ----------------------------------------------------------------------------------


@dataclass
class Reading:
    """One answer from Audience about one line."""

    heard: str
    final: bool  # the whole turn (False: words still being spoken)
    engine: str
    answer: AddresseeAnswer | None
    ms: float
    error: str | None = None

    def to_message(self) -> dict[str, Any]:
        a = self.answer
        return {
            "type": "audience",
            "final": self.final,
            "heard": self.heard,
            "engine": self.engine,
            "ms": round(self.ms, 1),
            "addressed": dict(a.addressed) if a else {},
            "unclear": a.unclear if a else None,
            "to_group": a.to_group if a else None,
            "error": self.error,
        }


def card(c: Character) -> PersonCard:
    """What the user can see of a character: their name, role and the features in the cast file."""
    features = [{"key": "role", "value": c.role.lower()}]
    features += [{"key": k, "value": v} for k, v in c.features.items()]
    return PersonCard.model_validate(
        {"id": c.id, "label": c.name, "aliases": list(c.aliases), "features": features}
    )


def last_user_to(lines: Sequence[Line]) -> list[str]:
    """Who the user's last line in `lines` was for."""
    return next((ln.to for ln in reversed(lines) if ln.speaker == USER), [])


class Audience:
    """SpellSpeak Audience, on the CPU, off the event loop (one line at a time)."""

    def __init__(self, cast: Sequence[Character], *, engine: str = "model", threads: int = 4):
        self.cast = list(cast)
        self.cards = {c.id: card(c) for c in cast}
        self.engine = "rules"
        self.error: str | None = None
        self._model: Any = None
        if engine == "model":
            try:
                from harness.addressee.classifier import load_classifier

                files = model_dir(AUDIENCE_DIR, AUDIENCE_FILES, AUDIENCE_HF)
                self._model = load_classifier(files, threads=threads, precision=PRECISION)
                self.engine = "model"
            except Exception as error:  # noqa: BLE001 — the rules baseline routes instead
                self.error = f"{type(error).__name__}: {error}"
                logger.warning(f"Audience: the model isn't loaded ({self.error}); using the rules")
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="audience")
        if self._model is not None:  # encode every card once, now, not on the first turn
            self._pool.submit(self._score, self.request("Hello.", []))

    @property
    def release(self) -> str:
        return AUDIENCE_HF[1]

    def request(self, text: str, history: Sequence[Line]) -> AddresseeRequest:
        """The model's input for `text`, said by the user after `history`. Lines said in a chorus
        are left out: they were said over each other, so none of them is the line before (the last
        of a chorus would otherwise catch the next vague line)."""
        said = [ln for ln in history if ln.text and ln.speaker != NOTE and ln.how != TOGETHER]
        said = said[-MAX_HISTORY:]
        last_to = last_user_to(history)
        last_one = last_to[0] if len(last_to) == 1 and last_to[0] in self.cards else None
        latest = said[-1] if said else None
        present = []
        for c in self.cast:
            facts = SpatialFacts(
                distance="near",
                in_group=True,
                last_spoke_with_you=None if last_one is None else c.id == last_one,
                asked_you=bool(
                    latest and latest.speaker == c.id and latest.text.rstrip().endswith("?")
                ),
            )
            present.append(self.cards[c.id].model_copy(update={"spatial": facts}))
        known = set(self.cards) | {USER}
        return AddresseeRequest(
            text=text[:MAX_TEXT],
            present=present,
            history=[
                HistoryLine(
                    speaker=ln.speaker,
                    to=[t for t in ln.to if t != ln.speaker and t in known],
                    text=ln.text[:MAX_TEXT],
                )
                for ln in said
            ],
        )

    def _score(self, req: AddresseeRequest) -> AddresseeAnswer:
        return self._model.answer(req) if self._model is not None else rules_answer(req)

    async def read(self, text: str, history: Sequence[Line], *, final: bool) -> Reading:
        text = normalize(text)
        started = time.perf_counter()
        try:
            req = self.request(text, history)
            loop = asyncio.get_running_loop()
            answer = await loop.run_in_executor(self._pool, self._score, req)
            error = None
        except Exception as e:  # noqa: BLE001 — the plan falls back
            logger.exception("Audience: reading failed")
            answer, error = None, f"{type(e).__name__}: {e}"
        ms = (time.perf_counter() - started) * 1000
        return Reading(text, final, self.engine, answer, ms, error)


# --- Plans -------------------------------------------------------------------------------------


@dataclass
class Take:
    """One line for a character to say, why, and the note it's given about the moment."""

    speaker: str
    reason: str  # addressed, several, group, chorus, unclear, fallback
    note: str | None = None

    @property
    def how(self) -> str:
        return TOGETHER if self.reason in ("chorus", "unclear") else SAID


@dataclass
class Plan:
    """What the room does: lines in turn, in order, or all at once (a chorus)."""

    takes: list[Take] = field(default_factory=list)
    together: bool = False
    why: str = ""
    addressed: list[str] = field(default_factory=list)  # who the user's line was for ([]: unclear)

    def to_message(self) -> dict[str, Any]:
        return {
            "why": self.why,
            "together": self.together,
            "speakers": [t.speaker for t in self.takes],
            "addressed": self.addressed,
        }


def in_turn(members: Sequence[str], transcript: Transcript, reason: str) -> list[Take]:
    """One line each, in order; each is told who was asked, and sees who has answered so far."""
    everyone = len(members) == len(transcript.cast)
    who = "everyone here" if everyone else names([transcript.label(m) for m in members])
    return [
        Take(m, reason, NOTE_IN_TURN.format(who=who, topics=transcript.cast[m].topics))
        for m in members
    ]


def plan(reading: Reading, line: Line, transcript: Transcript) -> Plan:
    """What the room does about the user's `line` (already in the transcript), given Audience's
    reading of it. Without a reading, whoever spoke last answers."""
    ids = list(transcript.cast)
    before = transcript.lines[: transcript.lines.index(line)] if line in transcript.lines else []
    last = next((ln for ln in reversed(before) if ln.by_character), None)
    last_to = last_user_to(before)
    last_one = last_to[0] if len(last_to) == 1 and last_to[0] in ids else None
    a = reading.answer
    if a is None:
        who = last_one or (last.speaker if last else ids[0])
        return Plan([Take(who, "fallback")], why="fallback", addressed=[who])

    if len(ids) == 1:  # alone with the user: whatever they say, it's to them
        return Plan([Take(ids[0], "addressed")], why="addressed", addressed=ids)
    ranked = sorted(ids, key=lambda c: a.addressed.get(c, 0.0), reverse=True)
    if a.to_group >= GROUP_FLOOR:
        if len(line.text.split()) <= CHORUS_MAX_WORDS:
            cast = transcript.cast
            takes = [Take(c, "chorus", NOTE_CHORUS.format(topics=cast[c].topics)) for c in ranked]
            return Plan(takes, together=True, why="chorus", addressed=ranked)
        return Plan(in_turn(ranked, transcript, "group"), why="group", addressed=ranked)
    if a.unclear >= UNCLEAR_FLOOR:
        maybe = [c for c in ranked if a.addressed[c] >= CANDIDATE_FLOOR] or ranked[:1]
        takes = [Take(c, "unclear", NOTE_WHO_ME) for c in maybe]
        return Plan(takes, together=len(takes) > 1, why="unclear", addressed=[])
    sure = [c for c in ranked if a.addressed[c] >= SURE_FLOOR]
    if len(sure) >= 2:
        return Plan(in_turn(sure, transcript, "several"), why="several", addressed=sure)
    maybe = [c for c in ranked if a.addressed[c] >= ADDRESSED_FLOOR]
    if not sure and len(maybe) >= 2:  # several could be meant, nobody for sure: "oi, you!"
        takes = [Take(c, "unclear", NOTE_WHO_ME) for c in maybe]
        return Plan(takes, together=True, why="unclear", addressed=[])
    top = ranked[0]
    if a.addressed[top] < PERSON_FLOOR and last_one is not None:
        return Plan([Take(last_one, "fallback")], why="fallback", addressed=[last_one])
    note = None
    if last is not None and last.speaker != top:
        note = NOTE_SWITCH.format(other=transcript.label(last.speaker))
    return Plan([Take(top, "addressed", note)], why="addressed", addressed=[top])
