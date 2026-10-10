"""SpellSpeak Tone in the room: what each line does to everyone it's said to or about.

Every line is read once, whoever says it: the user's as soon as Audience has said who it's for,
and each character's as it starts playing. Tone is given the line, the line before it, who says it,
who it's to, and everyone else present (the user and the characters, by name). It answers with the
speaker's emotion and, for each person, an act (praise, tease, insult, threat…) with an intensity
and a confidence. One read takes about 10 ms on the CPU, off the event loop.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from loguru import logger

import runtimes  # noqa: F401 — both models' runtimes, before their modules
from config import PRECISION, TONE_DIR, TONE_FILES, TONE_HF, USER, Character
from contracts.schemas.line_tags import LineInput, LineTags, is_hostile
from harness.expression.classifier import LineClassifier
from runtimes import model_dir

MAX_TEXT = 400  # the longest line the model reads
MAX_PREVIOUS = 480


@dataclass
class ToneReading:
    """Tone's reading of one line, with the people in it by id."""

    speaker: str
    to: str | None
    tags: LineTags | None
    ms: float
    error: str | None = None

    def acts(self) -> dict[str, Any]:
        if self.tags is None:
            return {}
        return {
            who: {
                "act": a.act,
                "intensity": a.intensity,
                "confidence": a.confidence,
                "hostile": is_hostile(a.act, a.intensity),
            }
            for who, a in self.tags.acts.items()
        }

    def emotion(self) -> dict[str, Any] | None:
        t = self.tags
        if t is None:
            return None
        return {
            "label": t.emotion,
            "intensity": t.emotion_intensity,
            "confidence": t.emotion_confidence,
        }


class Tone:
    """SpellSpeak Tone, on the CPU, off the event loop (one line at a time)."""

    def __init__(self, cast: Sequence[Character], *, threads: int = 4):
        self.cast = list(cast)
        # Tone reads people by the names said in the room; the user is `player`.
        self.names = {c.id: c.name for c in cast} | {USER: USER}
        self.ids = {name: who for who, name in self.names.items()}
        files = model_dir(TONE_DIR, TONE_FILES, TONE_HF)
        self._model = LineClassifier(files, threads=threads, precision=PRECISION)
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tone")
        self._pool.submit(self._model.tag, self.request(USER, None, "Hello.", None))  # warm up

    @property
    def release(self) -> str:
        return TONE_HF[1]

    def request(self, speaker: str, to: str | None, text: str, previous: str | None) -> LineInput:
        """The model's input: `speaker` (an id, or USER) says `text` to `to` (None: the room)."""
        targets = [self.names[w] for w in self.names if w != speaker]
        return LineInput(
            speaker=self.names[speaker],
            speaker_kind="player" if speaker == USER else "npc",
            to=self.names[to] if to is not None and to != speaker else None,
            targets=targets,
            text=text[:MAX_TEXT],
            previous=previous[:MAX_PREVIOUS] if previous else None,
        )

    def said(self, speaker: str, text: str) -> str:
        """A line as Tone reads it for `previous`: "Name: text"."""
        return f"{self.names.get(speaker, speaker)}: {text}"

    async def read(
        self, speaker: str, to: str | None, text: str, previous: str | None
    ) -> ToneReading:
        started = time.perf_counter()
        try:
            req = self.request(speaker, to, text, previous)
            loop = asyncio.get_running_loop()
            tags = await loop.run_in_executor(self._pool, self._model.tag, req)
            # Back to ids.
            tags = tags.model_copy(
                update={"acts": {self.ids[n]: a for n, a in tags.acts.items() if n in self.ids}}
            )
            error = None
        except Exception as e:  # noqa: BLE001 — a line unread moves nobody
            logger.exception("Tone: reading failed")
            tags, error = None, f"{type(e).__name__}: {e}"
        ms = (time.perf_counter() - started) * 1000
        return ToneReading(speaker, to, tags, ms, error)
