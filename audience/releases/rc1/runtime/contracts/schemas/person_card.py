"""Person card 0.1: what the player can see of one person in the scene.

A card is how the addressee model knows who is who. It holds only what the player could see or would call
someone, never what is true but hidden: a disguised elf is `race: human`, and a hood up makes `hair: hidden`.

- `label` is what the player would call them. The player may not know the name, so "the barkeep" is a valid
  label. `aliases` hold the other names they answer to (nicknames, titles, what the locals say). `id` is the
  harness's handle and is never shown to the model.
- `features` is an open list of `key: value` pairs; the set of keys is not fixed. The model reads them as text.
  `CORE_KEYS` are recommended, and the ones a harness can later fill from the engine. A game adds any key it
  likes. A value may be `hidden` (the player cannot see it) or `unknown`.
- `spatial` is optional, and every fact in it is optional. It is a closed set of plain bands, never raw engine
  numbers. `harness/addressee/bands.py` turns positions into these bands.
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

SCHEMA_VERSION = "person-card-0.1"

CardId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_.:-]*$", max_length=64)]
Label = Annotated[str, StringConstraints(min_length=1, max_length=40, strip_whitespace=True)]
FeatureKey = Annotated[str, StringConstraints(min_length=1, max_length=32, strip_whitespace=True)]
FeatureValue = Annotated[str, StringConstraints(min_length=1, max_length=80, strip_whitespace=True)]

# Recommended keys. Open: a card may use none of them and any others.
CORE_KEYS: tuple[str, ...] = (
    "role", "race", "presents as", "age", "build", "marks", "hair", "facial hair", "headwear", "clothing", "insignia",
    "holding", "carrying", "doing", "posture", "condition", "near", "with",
)
HIDDEN, UNKNOWN = "hidden", "unknown"

MAX_FEATURES = 16
MAX_ALIASES = 4

Distance = Literal["near", "mid", "far"]
DISTANCES: tuple[str, ...] = Distance.__args__


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Feature(Strict):
    key: FeatureKey
    value: FeatureValue

    @property
    def visible(self) -> bool:
        return self.value.lower() not in (HIDDEN, UNKNOWN)


class SpatialFacts(Strict):
    """What the game knows about where this person is relative to the player, in bands. None: not known."""

    distance: Distance | None = None
    in_view: bool | None = None              # inside the player's gaze cone when they started speaking
    in_group: bool | None = None             # in the player's current conversation group
    following: bool | None = None            # following the player
    asked_you: bool | None = None            # has a question waiting for the player's answer
    last_spoke_with_you: bool | None = None  # the last person the player was talking with

    @property
    def empty(self) -> bool:
        return all(v is None for v in self.model_dump().values())


class PersonCard(Strict):
    id: CardId
    label: Label
    aliases: list[Label] = Field(default=[], max_length=MAX_ALIASES)
    features: list[Feature] = Field(default=[], max_length=MAX_FEATURES)
    spatial: SpatialFacts | None = None

    @model_validator(mode="after")
    def _names(self) -> "PersonCard":
        names = [self.label.lower()] + [a.lower() for a in self.aliases]
        if len(set(names)) != len(names):
            raise ValueError("aliases must differ from the label and from each other")
        if self.id == "player":
            raise ValueError("`player` is reserved for the player, who has no card")
        return self

    def feature(self, key: str) -> list[str]:
        return [f.value for f in self.features if f.key.lower() == key.lower()]

    @property
    def names(self) -> list[str]:
        return [self.label, *self.aliases]

    def without_spatial(self) -> "PersonCard":
        return self.model_copy(update={"spatial": None})
