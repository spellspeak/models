"""Settings from the example's `.env` (beside `server/` and `client/`; variables already set win), the
cast from `characters.json` beside them, and every tunable the room uses."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

HERE = Path(__file__).resolve().parent
EXAMPLE = HERE.parent
REPO = EXAMPLE.parent.parent.parent
load_dotenv(EXAMPLE / ".env", override=False)  # before anything below reads the environment
# The repo's own .env too, for HF_TOKEN if one is set there.
load_dotenv(REPO / ".env", override=False)

# --- The models ----------------------------------------------------------------------------------

# Both read their 16-bit files: half the download of full precision, the same answers, the same speed.
PRECISION = "fp16"

# SpellSpeak Audience: who each of the user's turns is for. Its model files and reference runtime are
# a release folder of this repo; a relative AUDIENCE_DIR is from this example's folder.
AUDIENCE_DIR = (
    EXAMPLE / (os.getenv("AUDIENCE_DIR") or "../../../audience/releases/rc2.1")
).resolve()
AUDIENCE_FILES = ["encoder_fp16.onnx", "head_fp16.onnx", "tokenizer.json", "config.json"]
AUDIENCE_HF = ("spellspeak/audience", "rc2.1")

# SpellSpeak Tone: what every line does to each person it's said to or about, and how it sounds.
TONE_DIR = (EXAMPLE / (os.getenv("TONE_DIR") or "../../releases/rc2.1")).resolve()
TONE_FILES = ["model_fp16.onnx", "tokenizer.json", "config.json"]
TONE_HF = ("spellspeak/tone", "rc2.1")
# When a release folder has no model files (a git checkout), they come from Hugging Face, once
# (`runtimes.model_dir`).

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

# --- Feelings ------------------------------------------------------------------------------------

# How one person feels about another, 0 to 100 (`feelings.py`). Only what Tone is at least this sure
# of moves a feeling.
ACT_CONFIDENCE = 0.5
# A line read as an emotion at least this sure shows on its speaker's face.
EMOTION_CONFIDENCE = 0.5
# ...but one that goes against the mood they were voiced in (warm against cold or hostile, either way)
# must be read surer than this, and above low intensity. Tone can take a teasing promise ("keep
# talking like that and I might let you pick the route") for a threat, and read it as low anger
# (0.67); real anger after an insult reads 0.9 and more.
EMOTION_AGAINST_CONFIDENCE = 0.85
# A reaction shows on a face for this many lines said in the room (by anyone), unless something
# new comes along; then the face goes back to how they feel about the user.
MOOD_LINES = 3

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

# --- The characters' voices --------------------------------------------------------------------

# Eleven v4 Turbo, over ElevenLabs' Text-to-Dialogue WebSocket: it performs inline audio tags
# ("[angry] Get out."), and starts a line in about 100 ms.
ELEVENLABS_MODEL = "eleven_v4_turbo"
# How a character's mood is voiced: the tag put in front of their line (none for neutral). Tags are
# free text in square brackets; these are what each mood sounded most like when tried.
VOICE_TAGS = {
    "neutral": "",
    "happy": "[happy]",
    "amused": "[amused]",
    "angry": "[angry]",
    "sad": "[sad]",
    "afraid": "[nervously]",
    "surprised": "[surprised]",
    "disgusted": "[disgusted]",
    "contemptuous": "[sarcastically]",
}
# Strong anger is shouted.
VOICE_TAGS_HIGH = {"angry": "[shouts]"}


# --- The cast ----------------------------------------------------------------------------------

USER = "player"  # the user: the name both models reserve for the one playing


@dataclass(frozen=True)
class Temper:
    """How a character takes what's said to or about them: what moves their feelings, and how
    it shows on their face."""

    feelings: dict[str, int]  # how they feel about each person at the start (0 to 100)
    warms: float = 1.0  # how far kindness moves them
    hurts: float = 1.0  # how far hostility does
    reactions: dict[str, str] = field(default_factory=dict)  # act → mood, over `feelings.REACTIONS`


@dataclass(frozen=True)
class Character:
    id: str
    name: str
    role: str
    tagline: str
    topics: str
    voice: str  # ElevenLabs voice id
    temper: Temper
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
    """Who's in the garage, from `characters.json` (the client reads the same file): every
    character marked `present`. The others stay in the file, feelings and all, for later."""
    entries = [e for e in json.loads((EXAMPLE / "characters.json").read_text()) if e.get("present")]
    ids = [e["id"] for e in entries]
    if not 1 <= len(entries) <= 8 or len(set(ids)) != len(ids):
        raise ValueError("characters.json must have 1 to 8 present characters with distinct ids")
    cast = []
    for e in entries:
        people = {USER, *ids} - {e["id"]}
        missing = people - set(e["feelings"])
        if missing:
            raise ValueError(f"{e['id']} has no feelings about {sorted(missing)}")
        temper = e.get("temper", {})
        cast.append(
            Character(
                id=e["id"],
                name=e["name"],
                role=e["role"],
                tagline=e["tagline"],
                topics=e["topics"],
                voice=e["voice"],
                temper=Temper(
                    # Only about the people here: the user and whoever else is present.
                    feelings={k: int(v) for k, v in e["feelings"].items() if k in people},
                    warms=float(temper.get("warms", 1.0)),
                    hurts=float(temper.get("hurts", 1.0)),
                    reactions=dict(temper.get("reactions", {})),
                ),
                aliases=tuple(e.get("aliases", [])),
                features=dict(e.get("features", {})),
                keyterms=tuple(e.get("keyterms", [])),
            )
        )
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
    elevenlabs_api_key: str
    audience_engine: str  # "model" or "rules"
    threads: int  # for each model

    @classmethod
    def from_env(cls) -> Settings:
        engine = (os.getenv("AUDIENCE_ENGINE") or "model").strip().lower()
        if engine not in ("model", "rules"):
            raise SystemExit(f"AUDIENCE_ENGINE is {engine!r}: model or rules")
        return cls(
            openai_api_key=require("OPENAI_API_KEY"),
            openai_model=(os.getenv("OPENAI_MODEL") or OPENAI_MODEL).strip(),
            deepgram_api_key=require("DEEPGRAM_API_KEY"),
            elevenlabs_api_key=require("ELEVENLABS_API_KEY"),
            audience_engine=engine,
            threads=int(os.getenv("MODEL_THREADS") or 4),
        )


_logging_configured = False


def configure_logging(*, verbose: bool) -> None:
    """Once per process: BOT_LOG_LEVEL (INFO by default; DEBUG adds what was said), with the
    session id on every line."""
    global _logging_configured
    if _logging_configured:
        return
    _logging_configured = True
    logger.configure(extra={"session": "-"})
    if verbose:
        return
    logger.remove()
    logger.add(
        sys.stderr,
        level=os.getenv("BOT_LOG_LEVEL", "INFO").upper(),
        format=(
            "<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <7}</level> | "
            "<cyan>{extra[session]}</cyan> | {name}:{line} - <level>{message}</level>"
        ),
    )
