"""Line tags 0.1: what SpellSpeak Tone reads and returns.

The classifier reads one line spoken in a scene, by the player or by a character, and returns the speaker's
emotion and the social act toward each person in the scene. Feeling meters can add the acts up. The language model
voicing a character never needs any of this: the application reads the tags beside it.

- `targets` are everyone in the scene except the speaker, plus anyone named in the line whom the harness
  knows (closed list, never open-ended name matching). The reserved name `player` is the player.
- The emotion head is per line. The act head is per target, so `acts` has exactly one entry per target.
- Every output is a choice from a closed set. Confidences are optional: labels from people or the
  committee may carry none, the trained model always fills them.
- Intensity is a bin (low, medium, high). An act of `none` always has intensity `low`.
- A backchannel ("mm", "yeah", "go on") is not a turn: every act is `none` and the meters ignore it.

Line tags 0.2 (Tone rc2, revision r8) adds one optional per-line field, `exchange`: what kind of move the line makes
(asks, answers, hedges, doesnt_know, withholds, closes, other), for deciding who speaks next in a group conversation.
It lives in new classes (`LineTags02`, `LineTagRecord02`), so the 0.1 classes, their JSON schema and every 0.1 record
stay exactly as they were, and every 0.1 record also validates as 0.2.
"""
from __future__ import annotations

import pathlib
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

SCHEMA_VERSION = "line-tags-0.1"
PLAYER = "player"

Emotion = Literal["neutral", "happy", "amused", "angry", "sad", "afraid", "surprised", "disgusted", "contemptuous"]
EMOTIONS: tuple[str, ...] = Emotion.__args__

Act = Literal["insult", "threat", "accusation", "tease", "demand", "dismiss", "refusal", "request", "thanks", "praise",
              "apology", "comfort", "warning", "none"]
ACTS: tuple[str, ...] = Act.__args__

Intensity = Literal["low", "medium", "high"]
INTENSITIES: tuple[str, ...] = Intensity.__args__

# The hostile acts. `demand` counts only at high intensity.
HOSTILE_ACTS = ("insult", "threat", "accusation")
FRIENDLY_ACTS = ("thanks", "praise", "apology", "comfort")

Name = Annotated[str, StringConstraints(min_length=1, max_length=40, strip_whitespace=True)]
LineText = Annotated[str, StringConstraints(min_length=1, max_length=400)]
Probability = Annotated[float, Field(ge=0.0, le=1.0)]

MAX_TARGETS = 12  # the snapshot's cap on people per request (contracts/schemas/vocab.py)


def is_hostile(act: str, intensity: str) -> bool:
    """A hostile act for the scorecard and the meters' two-hit rule."""
    return act in HOSTILE_ACTS or (act == "demand" and intensity == "high")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LineInput(Strict):
    """One line and the people in the scene. What the harness sends to the classifier."""

    speaker: Name
    speaker_kind: Literal["player", "npc"]
    to: Name | None = None  # who it was said to; None: to the room
    targets: list[Name] = Field(min_length=1, max_length=MAX_TARGETS)
    text: LineText
    previous: str | None = Field(default=None, max_length=480)  # one earlier line, "Name: text"

    @model_validator(mode="after")
    def _cast(self) -> "LineInput":
        if len(set(self.targets)) != len(self.targets):
            raise ValueError("targets must be distinct")
        if self.speaker in self.targets:
            raise ValueError("the speaker is not a target of their own line")
        if (self.speaker == PLAYER) != (self.speaker_kind == "player"):
            raise ValueError("the player speaks as `player`, and only the player does")
        if self.to is not None and self.to not in self.targets:
            raise ValueError(f"`to` ({self.to}) must be one of the targets")
        return self


class ActTag(Strict):
    act: Act
    intensity: Intensity = "low"
    confidence: Probability | None = None  # r7: the chance the tag is right (hostile tags: that the line is hostile toward them)

    @model_validator(mode="after")
    def _none_is_low(self) -> "ActTag":
        if self.act == "none" and self.intensity != "low":
            raise ValueError("an act of none has intensity low")
        return self


class LineTags(Strict):
    """What the classifier returns for one line."""

    emotion: Emotion
    emotion_intensity: Intensity = "low"
    emotion_confidence: Probability | None = None  # r7: the chance the emotion is right
    acts: dict[Name, ActTag]
    backchannel: bool = False

    @model_validator(mode="after")
    def _neutral_and_backchannel(self) -> "LineTags":
        if self.emotion == "neutral" and self.emotion_intensity != "low":
            raise ValueError("a neutral emotion has intensity low")
        if self.backchannel and any(a.act != "none" for a in self.acts.values()):
            raise ValueError("a backchannel carries no act toward anyone")
        return self

    def hostile_toward(self) -> list[str]:
        return [t for t, a in self.acts.items() if is_hostile(a.act, a.intensity)]


class LineTagRecord(Strict):
    """A labelled line: the input, its tags, and where the label came from. Guide examples, committee labels and
    model predictions all use this record."""

    schema_version: Literal["line-tags-0.1"] = SCHEMA_VERSION
    line_id: Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_.:-]*$", max_length=120)]
    input: LineInput
    tags: LineTags
    label_source: Literal["guide", "committee", "person", "model"] = "guide"
    slices: list[Annotated[str, StringConstraints(pattern=r"^[a-z_]+$")]] = []  # e.g. sarcasm, interjection, group
    notes: str | None = None

    @model_validator(mode="after")
    def _one_act_per_target(self) -> "LineTagRecord":
        if set(self.tags.acts) != set(self.input.targets):
            missing = sorted(set(self.input.targets) - set(self.tags.acts))
            extra = sorted(set(self.tags.acts) - set(self.input.targets))
            raise ValueError(f"acts must cover exactly the targets (missing {missing}, extra {extra})")
        return self


EXAMPLES_PATH = pathlib.Path(__file__).resolve().parent / "examples" / "line-tags-0.1.examples.yaml"


def load_examples() -> list[LineTagRecord]:
    """The label guide's worked examples (kept with the training code; not part of a release)."""
    import yaml

    return [LineTagRecord.model_validate(r) for r in yaml.safe_load(EXAMPLES_PATH.read_text())]


# --- line-tags-0.2: the exchange head (rc2, revision r8) ----------------------------------------------------------

SCHEMA_VERSION_02 = "line-tags-0.2"

Exchange = Literal["asks", "answers", "hedges", "doesnt_know", "withholds", "closes", "other"]
EXCHANGES: tuple[str, ...] = Exchange.__args__
# After either of these, a question is still open: someone else may answer it.
STILL_OPEN = ("doesnt_know", "withholds")


class ExchangeTag(Strict):
    """What kind of move a line makes in the conversation, read with the line before it (guide 0.2)."""

    label: Exchange
    confidence: Probability | None = None  # the chance the label is right; labels from people or the committee may carry none


class LineTags02(LineTags):
    """What the classifier returns for one line under line-tags-0.2: the 0.1 tags plus the exchange move, when the
    model has the exchange head."""

    exchange: ExchangeTag | None = None


class LineTagRecord02(LineTagRecord):
    """A labelled line under line-tags-0.2. Every line-tags-0.1 record validates here unchanged; a record that carries
    an exchange label says line-tags-0.2."""

    schema_version: Literal["line-tags-0.1", "line-tags-0.2"] = SCHEMA_VERSION_02
    tags: LineTags02

    @model_validator(mode="after")
    def _exchange_needs_02(self) -> "LineTagRecord02":
        if self.tags.exchange is not None and self.schema_version != SCHEMA_VERSION_02:
            raise ValueError("`exchange` is a line-tags-0.2 field: the record must say schema_version line-tags-0.2")
        return self


EXAMPLES_02_PATH = pathlib.Path(__file__).resolve().parent / "examples" / "line-tags-0.2.examples.yaml"


def load_examples_02() -> list[LineTagRecord02]:
    """The exchange head's worked examples (kept with the training code; not part of a release)."""
    import yaml

    return [LineTagRecord02.model_validate(r) for r in yaml.safe_load(EXAMPLES_02_PATH.read_text())]
