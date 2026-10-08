"""SpellSpeak Audience in the room: who each user turn is for, and who answers it.

`Transcript` is the conversation as it happened: who said what, and who each line was for. Every
agent is shown the whole of it from their own viewpoint (`Transcript.view`), so nobody misses what was
said while someone else had the floor.

`Audience` asks the model who the user's line is for. Its request is the line, a card per agent
(what the user can see of them: `characters.json`), the last few lines with who they were for, and
what the room knows about where everyone is: all four stand in Neon Yard with the user (near, in the
group), the user may be looking at one of them (the client says who), and the transcript says who
the user spoke with last and who just asked them something. The model scores; `plan_route` decides:

- `unclear` at least `UNCLEAR_FLOOR`: the likeliest agent checks whether it was for them ("Who, me?").
- `to_group` at least `GROUP_FLOOR`: everyone answers in turn, likeliest first (`GROUP_MAX` at most).
- otherwise the likeliest agent answers, or, if even they are below `PERSON_FLOOR`, whoever the user
  spoke with last.

With no model files (or `AUDIENCE_ENGINE=rules`) the runtime's rules baseline scores instead: word
matching and the rules of evidence, instant, but blind to anything the words don't spell out.
"""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from config import (
    AUDIENCE_DIR,
    GROUP_FLOOR,
    GROUP_MAX,
    HF_REPO,
    HF_REVISION,
    MODEL_FILES,
    PERSON_FLOOR,
    UNCLEAR_FLOOR,
    Agent,
)

sys.path.insert(0, str(AUDIENCE_DIR / "runtime"))

from contracts.schemas.addressee import (  # noqa: E402
    MAX_HISTORY,
    PLAYER,
    AddresseeAnswer,
    AddresseeRequest,
    HistoryLine,
)
from contracts.schemas.person_card import PersonCard, SpatialFacts  # noqa: E402
from harness.addressee.rules import rules_answer  # noqa: E402

USER = PLAYER  # the user is the runtime's "player", who has no card
MAX_TEXT = 400  # the longest line the model reads

# What an agent is told about the moment, as a `[Note: …]` line at the end of their view.
NOTE_WELCOME = (
    "The person has just arrived in Neon Yard. Say hello and who you are, in one short sentence."
)
NOTE_GROUP_FIRST = "The person said that to everyone in Neon Yard. Give your own answer, briefly."
NOTE_GROUP_NEXT = (
    "The person said that to everyone in Neon Yard, and {others} answered. "
    "Now give your own answer, briefly, without repeating theirs."
)
NOTE_UNCLEAR = (
    "It isn't clear who the person said that to: it might have been you, or someone else in "
    "Neon Yard. Don't answer it or take it personally yet: check, in one short sentence, whether they "
    "meant you."
)
NOTE_CARRY_ON = "Carry on."
NOTE_JOINED = "The person arrives in Neon Yard."


def normalize(text: str) -> str:
    return " ".join(text.split())


def names(agents: Sequence[Agent]) -> str:
    """'Maya', 'Maya and Theo', 'Maya, Theo and Juno'."""
    n = [a.name for a in agents]
    return n[0] if len(n) == 1 else f"{', '.join(n[:-1])} and {n[-1]}"


@dataclass
class Line:
    speaker: str  # USER or an agent id
    text: str
    to: list[str] = field(default_factory=list)  # who it was for (agent ids, or USER); [] unknown
    interrupted: bool = False


class Transcript:
    """Who said what to whom, in order, and how each agent sees it."""

    def __init__(self, cast: Sequence[Agent]) -> None:
        self.cast = {c.id: c for c in cast}
        self.lines: list[Line] = []

    def add(
        self, speaker: str, text: str, *, to: Sequence[str] = (), interrupted: bool = False
    ) -> Line:
        line = Line(speaker, normalize(text), list(to), interrupted)
        self.lines.append(line)
        return line

    def label(self, speaker: str) -> str:
        return "User" if speaker == USER else self.cast[speaker].name

    def last_user_to(self) -> list[str]:
        """Who the user's last line was for."""
        return next((ln.to for ln in reversed(self.lines) if ln.speaker == USER), [])

    def view(self, me: str, note: str | None = None) -> list[dict[str, str]]:
        """The conversation as `me`'s LLM sees it: their own lines as assistant turns, everyone
        else's as user turns marked `[User]` or `[Name]`, and the moment's note last."""
        messages: list[dict[str, str]] = []

        def say(role: str, content: str) -> None:
            if messages and messages[-1]["role"] == role:
                messages[-1]["content"] += "\n" + content
            else:
                messages.append({"role": role, "content": content})

        for line in self.lines:
            if line.speaker == me:
                say("assistant", line.text + ("…" if line.interrupted else ""))
            else:
                cut = " (cut off)" if line.interrupted else ""
                say("user", f"[{self.label(line.speaker)}] {line.text}{cut}")
        if messages and messages[0]["role"] == "assistant":
            messages.insert(0, {"role": "user", "content": f"[Note: {NOTE_JOINED}]"})
        if note:
            say("user", f"[Note: {note}]")
        elif not messages or messages[-1]["role"] == "assistant":
            say("user", f"[Note: {NOTE_CARRY_ON}]")
        return messages


@dataclass
class Reading:
    """One answer from Audience about one line."""

    heard: str
    final: bool  # the whole turn (False: words still being spoken)
    engine: str
    answer: AddresseeAnswer | None
    ms: float
    error: str | None = None

    def top(self) -> tuple[str | None, float]:
        if self.answer is None:
            return None, 0.0
        best = self.answer.top()
        return best, self.answer.addressed[best]

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


@dataclass
class Cue:
    """An agent's turn: who, why, and what they're told about the moment."""

    speaker: str
    reason: str  # welcome, addressed, group, unclear, fallback, continue
    note: str | None = None


@dataclass
class Route:
    kind: str  # one, group, unclear
    reason: str
    to: list[str]  # who the user's line was for, as the transcript records it
    cues: list[Cue]

    def to_message(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "reason": self.reason,
            "speakers": [c.speaker for c in self.cues],
        }


def plan_route(reading: Reading, cast: Sequence[Agent], last_to: Sequence[str]) -> Route:
    """Who answers the user's line, from Audience's scores (the module docstring has the rules)."""
    by_id = {c.id: c for c in cast}
    last_one = last_to[0] if len(last_to) == 1 and last_to[0] in by_id else None
    a = reading.answer
    if a is None:  # Audience failed: whoever the user spoke with last, else the first agent
        who = last_one or cast[0].id
        return Route("one", "fallback", [who], [Cue(who, "fallback")])

    ranked = sorted(a.addressed, key=lambda i: a.addressed[i], reverse=True)
    if a.unclear >= UNCLEAR_FLOOR:
        return Route("unclear", "unclear", [], [Cue(ranked[0], "unclear", NOTE_UNCLEAR)])
    if a.to_group >= GROUP_FLOOR:
        speakers = ranked[: max(1, min(GROUP_MAX, len(ranked)))]
        cues = [Cue(speakers[0], "group", NOTE_GROUP_FIRST)]
        for i, s in enumerate(speakers[1:], start=1):
            before = [by_id[p] for p in speakers[:i]]
            cues.append(Cue(s, "group", NOTE_GROUP_NEXT.format(others=names(before))))
        return Route("group", "group", [c.id for c in cast], cues)
    top = ranked[0]
    if a.addressed[top] < PERSON_FLOOR and last_one is not None:
        return Route("one", "fallback", [last_one], [Cue(last_one, "fallback")])
    return Route("one", "addressed", [top], [Cue(top, "addressed")])


def card(agent: Agent) -> PersonCard:
    """What the user can see of an agent: their name, role and the features in `characters.json`."""
    features = [{"key": "role", "value": agent.role.lower()}]
    features += [{"key": k, "value": v} for k, v in agent.features.items()]
    return PersonCard.model_validate(
        {"id": agent.id, "label": agent.name, "aliases": list(agent.aliases), "features": features}
    )


def model_dir() -> Path:
    """Where the model files are: the release folder if it has them, else Hugging Face's cache,
    downloading them the first time (the repo is private for now: HF_TOKEN, or `hf auth login`)."""
    if all((AUDIENCE_DIR / f).exists() for f in MODEL_FILES):
        return AUDIENCE_DIR
    from huggingface_hub import snapshot_download

    logger.info(f"Audience: no model files in {AUDIENCE_DIR}; fetching {HF_REPO}@{HF_REVISION}")
    return Path(snapshot_download(HF_REPO, revision=HF_REVISION, allow_patterns=MODEL_FILES))


class Audience:
    """SpellSpeak Audience, on the CPU, off the event loop (one line at a time)."""

    def __init__(self, cast: Sequence[Agent], *, engine: str = "model", threads: int = 4) -> None:
        self.cast = list(cast)
        self.cards = {c.id: card(c) for c in cast}
        self.engine = "rules"
        self.error: str | None = None
        self._model: Any = None
        if engine == "model":
            try:
                from harness.addressee.classifier import load_classifier

                self._model = load_classifier(model_dir(), threads=threads)
                self.engine = "model"
            except Exception as error:  # noqa: BLE001 — the rules baseline routes instead
                self.error = f"{type(error).__name__}: {error}"
                logger.warning(f"Audience: the model isn't loaded ({self.error}); using the rules")
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="audience")
        if self._model is not None:  # encode every card once, now, not on the first turn
            self._pool.submit(self._score, self.request("Hello.", Transcript(cast)))

    @property
    def release(self) -> str:
        return AUDIENCE_DIR.name

    def request(
        self, text: str, transcript: Transcript, *, looking: str | None = None
    ) -> AddresseeRequest:
        """The model's input for `text`, said by the user now."""
        history = [ln for ln in transcript.lines if ln.text][-MAX_HISTORY:]
        last_to = transcript.last_user_to()
        last_one = last_to[0] if len(last_to) == 1 and last_to[0] in self.cards else None
        latest = history[-1] if history else None
        present = []
        for c in self.cast:
            facts = SpatialFacts(
                distance="near",
                in_group=True,
                in_view=None if looking is None else c.id == looking,
                last_spoke_with_you=None if last_one is None else c.id == last_one,
                asked_you=bool(
                    latest and latest.speaker == c.id and latest.text.rstrip().endswith("?")
                ),
            )
            present.append(self.cards[c.id].model_copy(update={"spatial": facts}))
        return AddresseeRequest(
            text=text[:MAX_TEXT],
            present=present,
            history=[
                HistoryLine(
                    speaker=ln.speaker,
                    to=[t for t in ln.to if t != ln.speaker],
                    text=ln.text[:MAX_TEXT],
                )
                for ln in history
            ],
        )

    def _score(self, req: AddresseeRequest) -> AddresseeAnswer:
        return self._model.answer(req) if self._model is not None else rules_answer(req)

    async def read(
        self, text: str, transcript: Transcript, *, looking: str | None, final: bool
    ) -> Reading:
        text = normalize(text)
        started = time.perf_counter()
        try:
            req = self.request(text, transcript, looking=looking)
            loop = asyncio.get_running_loop()
            answer = await loop.run_in_executor(self._pool, self._score, req)
            error = None
        except Exception as e:  # noqa: BLE001 — the route falls back
            logger.exception("Audience: reading failed")
            answer, error = None, f"{type(e).__name__}: {e}"
        ms = (time.perf_counter() - started) * 1000
        return Reading(text, final, self.engine, answer, ms, error)

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
