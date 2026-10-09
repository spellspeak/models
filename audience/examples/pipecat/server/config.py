"""Settings from the example's `.env` (beside `server/` and `client/`; variables already set win), the
cast from `characters.json` beside them, and every tunable the room uses."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
EXAMPLE = HERE.parent
load_dotenv(EXAMPLE / ".env", override=False)  # before anything below reads the environment
# The repo's own .env too, for HF_TOKEN if one is set there.
load_dotenv(EXAMPLE.parent.parent.parent / ".env", override=False)

# --- SpellSpeak Audience -------------------------------------------------------------------------

# Its model files and reference runtime: a release folder of this repo. A relative AUDIENCE_DIR is
# from this example's folder, where the .env is.
AUDIENCE_DIR = (EXAMPLE / (os.getenv("AUDIENCE_DIR") or "../../releases/rc1")).resolve()
# When the release folder has no model files (a git checkout), they come from Hugging Face, once.
MODEL_FILES = ["encoder.onnx", "head.onnx", "tokenizer.json", "config.json"]
HF_REPO, HF_REVISION = "spellspeak/audience", "rc1"

# How a reading becomes a plan (`audience.py`, `plan`):
GROUP_FLOOR = 0.5  # to_group at least this: everyone answers...
CHORUS_MAX_WORDS = 7  # ...all at once if the line is this short ("hey, all of you!"), else in turn
UNCLEAR_FLOOR = 0.5  # unclear at least this: whoever it might be for asks "Who, me?" at once
CANDIDATE_FLOOR = 0.3  # ...those this likely, at least
# Several people fairly likely but nobody sure ("oi, you!"): as unclear, everyone it might be for asks.
# Two or more this sure ("Nova and Kai, …") are each addressed, and answer in turn.
SURE_FLOOR = 0.85
ADDRESSED_FLOOR = 0.5  # one character this likely is addressed
PERSON_FLOOR = 0.35  # the likeliest below this: whoever the user spoke with last answers instead

# --- Workers -----------------------------------------------------------------------------------

ROOM = "room"  # the main worker: transport, STT, the director; each character is a worker too

# --- The user's turn ---------------------------------------------------------------------------

# When it ends is Deepgram Flux's call (services.py). The room only makes sure nobody talks over
# the user: whenever their voice starts again after their turn ended, it waits for those words to
# become a turn (the transcript trails the voice), up to MORE_MAX_S, or for TRANSCRIPT_LAG_S after
# the voice stops without one (a cough). A turn that began within MERGE_GAP_S of the last one
# ending, with nothing heard in between, is read as one turn.
MORE_MAX_S = 3.0
TRANSCRIPT_LAG_S = 0.8
MERGE_GAP_S = 2.0
MIN_WORDS_TO_INTERRUPT = 2  # while anyone is talking: "hang on" takes the floor, "haha" doesn't

# --- The floor ---------------------------------------------------------------------------------

TURN_GAP_S = 0.25  # the beat between one speaker finishing and the next starting
CHORUS_STAGGER_S = 1.0  # a chorus starts spread over this long from the first voice, as people do

# --- Lines over the bus ------------------------------------------------------------------------

SPEAK_JOB = "speak"
SPEAK_TIMEOUT_S = 45.0  # writing and voicing one line, however long it waits for its turn
WRITE_TIMEOUT_S = 15.0  # a character that hasn't written its line by then says nothing
VOICE_TIMEOUT_S = 15.0  # ...nor heard its TTS finish: the line is taken as voiced
# A line that has stopped playing but whose character hasn't said it's all sent is taken as
# finished after this long, so nobody waiting on it is held up for good.
FINISH_GRACE_S = 2.0

# --- The characters' LLM -----------------------------------------------------------------------

OPENAI_MODEL = "gpt-6-luna"
# Luna reasons before it writes unless told not to: "none" starts a line in ~0.75 s, like gpt-4o-mini,
# and the lines are no worse for it (at its default, ~1.6 s). Luna takes no temperature.
LLM_REASONING_EFFORT = "none"
LLM_TOKENS = 160
LLM_HISTORY_LINES = 40  # the most of the conversation a character is shown, in lines
DEEPGRAM_STT_MODEL = "flux-general-en"


@dataclass(frozen=True)
class Character:
    id: str
    name: str
    role: str
    tagline: str
    topics: str
    voice: str  # Deepgram Aura-2 voice
    aliases: tuple[str, ...] = ()
    features: dict[str, str] = field(default_factory=dict)  # what the user can see of them
    keyterms: tuple[str, ...] = ()  # words Flux listens out for, beyond their name (services.py)

    def looks(self) -> str:
        return ", ".join(f"{k} {v}" for k, v in self.features.items()) or "nothing in particular"

    def brief(self) -> str:
        return (
            f"{self.name}, the {self.role.lower()}: {self.tagline} Knows best: {self.topics}. "
            f"({self.looks()})"
        )


def load_cast() -> list[Character]:
    """The four, from `characters.json` (the client reads the same file)."""
    entries = json.loads((EXAMPLE / "characters.json").read_text())
    cast = [
        Character(
            id=e["id"],
            name=e["name"],
            role=e["role"],
            tagline=e["tagline"],
            topics=e["topics"],
            voice=e["voice"],
            aliases=tuple(e.get("aliases", [])),
            features=dict(e.get("features", {})),
            keyterms=tuple(e.get("keyterms", [])),
        )
        for e in entries
    ]
    if not 2 <= len(cast) <= 8 or len({c.id for c in cast}) != len(cast):
        raise ValueError("characters.json must list 2 to 8 characters with distinct ids")
    return cast


def require(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise SystemExit(f"{name} is not set (copy .env.example to .env, beside server/)")
    return value


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str
    deepgram_api_key: str
    audience_engine: str  # "model" or "rules"
    audience_threads: int

    @classmethod
    def from_env(cls) -> Settings:
        engine = (os.getenv("AUDIENCE_ENGINE") or "model").strip().lower()
        if engine not in ("model", "rules"):
            raise SystemExit(f"AUDIENCE_ENGINE is {engine!r}: model or rules")
        return cls(
            openai_api_key=require("OPENAI_API_KEY"),
            openai_model=(os.getenv("OPENAI_MODEL") or OPENAI_MODEL).strip(),
            deepgram_api_key=require("DEEPGRAM_API_KEY"),
            audience_engine=engine,
            audience_threads=int(os.getenv("AUDIENCE_THREADS") or 4),
        )
