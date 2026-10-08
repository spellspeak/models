"""Addressee 0.1: who a player line was said to.

The harness sends a request: the player's line, a card for each person present (contracts/schemas/person_card.py)
and the last few lines of the conversation. The model answers with one probability per person, a probability
that the words and facts do not pick anyone out (`unclear`), and a probability that the line is for the whole
group the player is talking with (`to_group`). It scores; it never decides: the harness decides who speaks.

Labels (`AddresseeLabel`) are what the rules of evidence (harness/addressee/evidence.py) give. A clear line lists
who it was said to. A vague line lists who it could have been said to, so a model can learn that "You lied to me."
with three people present is a third each, and the harness can play "Who, me?" instead of guessing.
"""
from __future__ import annotations

import pathlib
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from contracts.schemas.person_card import CardId, PersonCard

SCHEMA_VERSION = "addressee-0.1"
PLAYER = "player"

MAX_PRESENT = 8   # the snapshot's `present` cap (contracts/schemas/vocab.py)
MAX_HISTORY = 4   # the last few lines of the conversation

LineText = Annotated[str, StringConstraints(min_length=1, max_length=400)]
Probability = Annotated[float, Field(ge=0.0, le=1.0)]
Who = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_.:-]*$", max_length=64)]  # a card id or "player"

# How the line picks out who it is for (the rules of evidence). The benchmark slices on these.
Kind = Literal["name", "alias", "role", "appearance", "item", "activity", "place", "neighbour", "several", "group",
               "answer", "continuation", "correction", "switch", "vague", "nobody",
               "greeting", "question"]  # rule 5: simple harmless lines
KINDS: tuple[str, ...] = Kind.__args__
# What the spatial facts do in this example.
SpatialPattern = Literal["none", "agree", "contradict", "decide", "conflict", "neutral"]
SPATIAL_PATTERNS: tuple[str, ...] = SpatialPattern.__args__


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HistoryLine(Strict):
    """An earlier line in this conversation, oldest first. `to` empty: said to the room, or not known."""

    speaker: Who
    to: list[Who] = Field(default=[], max_length=MAX_PRESENT)
    text: LineText


class AddresseeRequest(Strict):
    """What the harness sends: the player's line, the people present, and the last few lines."""

    speaker: Literal["player"] = PLAYER
    text: LineText
    present: list[PersonCard] = Field(min_length=1, max_length=MAX_PRESENT)
    history: list[HistoryLine] = Field(default=[], max_length=MAX_HISTORY)

    @model_validator(mode="after")
    def _people(self) -> "AddresseeRequest":
        ids = [c.id for c in self.present]
        if len(set(ids)) != len(ids):
            raise ValueError("present ids must be distinct")
        known = set(ids) | {PLAYER}
        for h in self.history:
            if h.speaker not in known or any(t not in known for t in h.to):
                raise ValueError("history lines name only the player and people present")
            if h.speaker in h.to:
                raise ValueError("a history line is not said to its own speaker")
        return self

    def card(self, cid: str) -> PersonCard:
        return next(c for c in self.present if c.id == cid)

    @property
    def ids(self) -> list[str]:
        return [c.id for c in self.present]

    @property
    def has_spatial(self) -> bool:
        return any(c.spatial is not None and not c.spatial.empty for c in self.present)

    def text_only(self) -> "AddresseeRequest":
        """The same request with every spatial fact removed (the text-only input mode)."""
        return self.model_copy(update={"present": [c.without_spatial() for c in self.present]})


class AddresseeAnswer(Strict):
    """What the model returns. `addressed` has exactly one entry per person present."""

    addressed: dict[CardId, Probability]
    unclear: Probability
    to_group: Probability

    def top(self) -> str:
        return max(self.addressed, key=self.addressed.get)


class AddresseeLabel(Strict):
    """The answer the rules of evidence give. Clear: who it was said to. Vague: who it could have been said to."""

    addressed: list[CardId] = Field(min_length=1, max_length=MAX_PRESENT)
    vague: bool = False
    group: bool = False

    @model_validator(mode="after")
    def _shape(self) -> "AddresseeLabel":
        if len(set(self.addressed)) != len(self.addressed):
            raise ValueError("addressed ids must be distinct")
        if self.vague and self.group:
            raise ValueError("a group line is clear: everyone in the group")
        if self.vague and len(self.addressed) < 2:
            raise ValueError("a vague line lists at least two people it could be for")
        return self

    def targets(self, ids: list[str]) -> dict[str, float]:
        """Per-person training targets: 1 for each addressed person; 1/k for each of k candidates when vague."""
        share = 1.0 / len(self.addressed) if self.vague else 1.0
        return {i: (share if i in self.addressed else 0.0) for i in ids}


class AddresseeRecord(Strict):
    """A labelled line: the request, its label, and how the line picks its people out. Worked examples,
    constructed lines, committee labels and the spatial suite all use this record."""

    schema_version: Literal["addressee-0.1"] = SCHEMA_VERSION
    line_id: Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_.:-]*$", max_length=120)]
    request: AddresseeRequest
    label: AddresseeLabel
    kind: Kind
    spatial: SpatialPattern = "none"
    label_source: Literal["guide", "construction", "committee", "person", "model"] = "guide"
    slices: list[Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]+$")]] = []
    notes: str | None = None

    @model_validator(mode="after")
    def _consistent(self) -> "AddresseeRecord":
        ids = set(self.request.ids)
        if not set(self.label.addressed) <= ids:
            raise ValueError(f"label names people not present: {sorted(set(self.label.addressed) - ids)}")
        if len(ids) == 1 and self.label.vague:
            raise ValueError("with one person present a line is never vague (rule 1)")
        if (self.spatial == "none") == self.request.has_spatial:
            raise ValueError("spatial is `none` exactly when no card carries a spatial fact")
        return self


EXAMPLES_PATH = pathlib.Path(__file__).resolve().parent / "examples" / "addressee-0.1.examples.yaml"


def load_examples() -> list[AddresseeRecord]:
    """The worked examples (examples/ next to this file, not part of a release). The file defines its cards once
    under `cards` and reuses them with YAML anchors."""
    import yaml

    return [AddresseeRecord.model_validate(r) for r in yaml.safe_load(EXAMPLES_PATH.read_text())["examples"]]
