"""Settings from the example's `.env` (beside `server/` and `client/`; variables already set win), the four agents from `characters.json`
beside `server/` and `client/`, and the tunables the room uses."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
EXAMPLE = HERE.parent
load_dotenv(EXAMPLE / ".env", override=False)  # before anything below reads the environment
# The repo's own .env too, for HF_TOKEN: the model files on Hugging Face are private for now.
load_dotenv(EXAMPLE.parent.parent.parent / ".env", override=False)

# Audience's model files and reference runtime: a release folder of this repo. A relative
# AUDIENCE_DIR is from this example's folder, where the .env is.
AUDIENCE_DIR = (EXAMPLE / (os.getenv("AUDIENCE_DIR") or "../../releases/rc1")).resolve()
# When the release folder has no model files (a git checkout), they come from Hugging Face, once.
MODEL_FILES = ["encoder.onnx", "head.onnx", "tokenizer.json", "config.json"]
HF_REPO, HF_REVISION = "spellspeak/audience", "rc1"

ROOM = "room"  # the main worker: transport, STT, the router, TTS

# --- Routing (`audience.py`) --------------------------------------------------------------------

UNCLEAR_FLOOR = 0.5  # unclear at least this: the likeliest agent asks "Who, me?"
GROUP_FLOOR = 0.5  # to_group at least this: everyone answers, likeliest first
PERSON_FLOOR = 0.35  # the top agent below this: whoever the user spoke to last answers instead
GROUP_MAX = 4  # agents who answer a line for the group (1 to 4)
HANDOVER_WAIT_S = 10.0  # the next answer waits at most this long for the one before to play

# --- The agents' LLM -----------------------------------------------------------------------------

OPENAI_MODEL = "gpt-4o-mini"
LLM_TEMPERATURE = 0.8
LLM_TOKENS = 150
DEEPGRAM_STT_MODEL = "flux-general-en"


@dataclass(frozen=True)
class Agent:
    id: str
    name: str
    role: str
    tagline: str
    topics: str
    voice: str  # Deepgram Aura-2 voice
    aliases: tuple[str, ...] = ()
    features: dict[str, str] = field(default_factory=dict)  # what the user can see of them

    def brief(self) -> str:
        return f"{self.name}, the {self.role.lower()}: {self.tagline}"


def load_cast() -> list[Agent]:
    """The four agents, from `characters.json` (the client reads the same file)."""
    entries = json.loads((EXAMPLE / "characters.json").read_text())
    cast = [
        Agent(
            id=e["id"],
            name=e["name"],
            role=e["role"],
            tagline=e["tagline"],
            topics=e["topics"],
            voice=e["voice"],
            aliases=tuple(e.get("aliases", [])),
            features=dict(e.get("features", {})),
        )
        for e in entries
    ]
    if not 2 <= len(cast) <= 8 or len({c.id for c in cast}) != len(cast):
        raise ValueError("characters.json must list 2 to 8 agents with distinct ids")
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
