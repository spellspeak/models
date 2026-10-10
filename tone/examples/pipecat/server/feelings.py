"""How everyone feels about everyone, moved by what Tone reads in each line, and the face each
character shows for it.

`Feelings` keeps a matrix: how each character feels about the user and about each of the others,
0 to 100, starting where `characters.json` puts them. Every line is read by Tone, whoever says it,
and each act toward someone moves *that* person's feeling about the speaker: the user teases Nova,
Nova warms or cools to the user; Kai insults Nova, Nova cools to Kai. How far depends on the act,
its intensity and the person taking it (`warms`, `hurts`). An apology only wins back what the
speaker has cost them: "Sorry, I crashed your bike" makes up for nothing that was said, so it moves
nothing. The user's own feelings aren't kept.

Each character also has a mood, one of Tone's nine emotions, which is the face their portrait shows
and the tag their voice is given:

- **A reaction**: something said to or about them (an insult makes them angry, praise happy; each
  character can react their own way, `reactions` in `characters.json`), held for MOOD_LINES lines.
- **What they express**: the emotion Tone reads in their own line, as they say it, if Tone is sure
  of it (surer still when it goes against the mood they were voiced in: warm against cold or
  hostile, either way). It lasts until
  someone else speaks: it's what they did, not what they feel next, so it never steers their next
  line (told "you're angry" because they just sounded angry, a character stays angry for good).
- **At rest**: how they feel about the user (happy if fond, contemptuous if they can't stand them).

A character's next line is voiced, and they're told they feel, as their mood is when they're asked
for it: a reaction to what was just said, or their mood at rest.

This is the small version, for the example: a game's feelings would have more meters (trust,
affection, fear, respect), buffers, and slower moods.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from config import (
    ACT_CONFIDENCE,
    EMOTION_AGAINST_CONFIDENCE,
    EMOTION_CONFIDENCE,
    MOOD_LINES,
    USER,
    VOICE_TAGS,
    VOICE_TAGS_HIGH,
    Character,
)

if TYPE_CHECKING:
    from contracts.schemas.line_tags import LineTags


# Points at medium intensity. Hostile acts cost more than kind ones give: a feeling is easier to lose
# than to win.
EFFECTS = {
    "praise": 8,
    "comfort": 7,
    "thanks": 6,
    "apology": 5,
    "request": 0,
    "warning": 0,
    "none": 0,
    "tease": -2,
    "refusal": -2,
    "demand": -4,
    "dismiss": -5,
    "accusation": -8,
    "insult": -10,
    "threat": -12,
}
INTENSITY = {"low": 0.75, "medium": 1.0, "high": 1.5}

# Which way each mood leans, to tell when what a line expresses goes against the mood it was voiced in.
LEANS = {
    "happy": "warm",
    "amused": "warm",
    "sad": "cold",
    "afraid": "cold",
    "angry": "hostile",
    "disgusted": "hostile",
    "contemptuous": "hostile",
}


def against(voiced: str, expressed: str) -> bool:
    """Whether `expressed` goes against `voiced`: one warm, the other cold or hostile."""
    a, b = LEANS.get(voiced), LEANS.get(expressed)
    return a is not None and b is not None and (a == "warm") != (b == "warm")


# How an act said to or about someone shows on their face, unless they react their own way. None:
# no reaction (a request, nothing at all).
REACTIONS: dict[str, str | None] = {
    "praise": "happy",
    "comfort": "happy",
    "thanks": "happy",
    "apology": "neutral",
    "tease": "amused",
    "refusal": "sad",
    "dismiss": "sad",
    "demand": "contemptuous",
    "accusation": "angry",
    "insult": "angry",
    "threat": "afraid",
    "warning": "surprised",
    "request": None,
    "none": None,
}

# What the act was, for the character's note: "Kai just insulted you".
DONE = {
    "praise": "praised",
    "comfort": "comforted",
    "thanks": "thanked",
    "apology": "apologised to",
    "tease": "teased",
    "refusal": "turned down",
    "dismiss": "brushed off",
    "demand": "made demands of",
    "accusation": "accused",
    "insult": "insulted",
    "threat": "threatened",
    "warning": "warned",
}


def resting(feeling: int) -> str:
    """The face at rest, from how they feel about the user."""
    if feeling >= 75:
        return "happy"
    if feeling >= 35:
        return "neutral"
    return "contemptuous"


def words(feeling: int) -> str:
    if feeling < 25:
        return "can't stand them"
    if feeling < 45:
        return "wary of them"
    if feeling < 60:
        return "no strong feelings"
    if feeling < 80:
        return "like them"
    return "very fond of them"


@dataclass
class Mood:
    mood: str = "neutral"
    intensity: str = "low"
    why: str = "rest"  # rest, reaction or expressed
    by: str | None = None  # who caused a reaction
    act: str | None = None  # ...with what
    left: int = 0  # lines it holds for

    def to_message(self) -> dict[str, Any]:
        return {
            "mood": self.mood,
            "intensity": self.intensity,
            "why": self.why,
            "by": self.by,
            "act": self.act,
        }


@dataclass
class Change:
    who: str  # whose feeling moved
    toward: str  # about whom
    change: int
    value: int
    act: str

    def to_message(self) -> dict[str, Any]:
        return {
            "from": self.who,
            "toward": self.toward,
            "change": self.change,
            "value": self.value,
            "act": self.act,
        }


@dataclass
class Update:
    """What one line did: feelings moved, and faces changed."""

    changes: list[Change] = field(default_factory=list)
    moods: dict[str, Mood] = field(default_factory=dict)


class Feelings:
    def __init__(self, cast: Sequence[Character]) -> None:
        self.cast = {c.id: c for c in cast}
        self.value: dict[str, dict[str, int]] = {c.id: dict(c.temper.feelings) for c in cast}
        # What each has lost to each other person and not yet had an apology for.
        self.owed: dict[str, dict[str, int]] = {c.id: {} for c in cast}
        self.moods: dict[str, Mood] = {c.id: Mood(resting(self.value[c.id][USER])) for c in cast}

    def matrix(self) -> dict[str, dict[str, int]]:
        return {who: dict(row) for who, row in self.value.items()}

    def faces(self) -> dict[str, dict[str, Any]]:
        return {who: m.to_message() for who, m in self.moods.items()}

    def label(self, who: str) -> str:
        return "the person" if who == USER else self.cast[who].name

    def on_line(self, speaker: str, tags: LineTags) -> Update:
        """Apply one line Tone has read, said by `speaker` (USER or a character id)."""
        update = Update()
        before = {who: (m.mood, m.intensity) for who, m in self.moods.items()}
        voiced = self.moods[speaker].mood if speaker in self.moods else "neutral"
        # Reactions fade with every line said in the room; what someone expressed ends when
        # someone else speaks.
        for who, m in self.moods.items():
            if m.why == "rest":
                continue
            m.left -= 1
            if m.left <= 0 or (m.why == "expressed" and who != speaker):
                self.moods[who] = Mood(resting(self.value[who][USER]))

        if not tags.backchannel:
            for who, tag in tags.acts.items():
                if who not in self.cast or who == speaker:
                    continue
                if tag.confidence is not None and tag.confidence < ACT_CONFIDENCE:
                    continue
                c = self.cast[who]
                # How they feel about the speaker.
                delta = EFFECTS[tag.act] * INTENSITY[tag.intensity]
                delta *= c.temper.warms if delta > 0 else c.temper.hurts
                owed = self.owed[who].get(speaker, 0)
                if tag.act == "apology":
                    delta = min(delta, owed)  # it wins back what was lost, no more
                effect = round(delta)
                was = self.value[who][speaker]
                now = max(0, min(100, was + effect))
                change = now - was
                if change < 0 or tag.act == "apology":
                    self.owed[who][speaker] = owed - change  # lost, or won back
                if change:
                    self.value[who][speaker] = now
                    update.changes.append(Change(who, speaker, change, now, tag.act))
                if tag.act == "apology" and not effect:
                    continue  # nothing to make up for: it doesn't land, and shows on no face
                # How it shows on their face.
                face = c.temper.reactions.get(tag.act, REACTIONS.get(tag.act))
                if face is not None:
                    self.moods[who] = Mood(
                        face, tag.intensity, "reaction", speaker, tag.act, MOOD_LINES
                    )

        # The speaker shows what they say, if Tone is sure of it; surer, if it goes against the mood
        # they were voiced in.
        if speaker in self.cast and tags.emotion != "neutral":
            confidence = tags.emotion_confidence
            if against(voiced, tags.emotion):
                sure = (
                    confidence is not None
                    and confidence >= EMOTION_AGAINST_CONFIDENCE
                    and tags.emotion_intensity != "low"
                )
            else:
                sure = confidence is None or confidence >= EMOTION_CONFIDENCE
            if sure:
                self.moods[speaker] = Mood(
                    tags.emotion, tags.emotion_intensity, "expressed", left=MOOD_LINES
                )

        # Anyone at rest whose feeling about the user moved may rest differently now.
        for who, m in self.moods.items():
            if m.why == "rest":
                m.mood = resting(self.value[who][USER])
        update.moods = {
            who: m for who, m in self.moods.items() if (m.mood, m.intensity) != before[who]
        }
        return update

    def voice_tag(self, who: str) -> str:
        """The audio tag a character's next line opens with, for their mood."""
        m = self.moods[who]
        if m.intensity == "high" and m.mood in VOICE_TAGS_HIGH:
            return VOICE_TAGS_HIGH[m.mood]
        return VOICE_TAGS.get(m.mood, "")

    def note(self, who: str) -> str:
        """What a character is told about their feelings, before they write a line."""
        row = self.value[who]
        about = "; ".join(
            f"{self.label(other)}: {words(v)} ({v}/100)"
            for other, v in sorted(row.items(), key=lambda kv: kv[0] != USER)
        )
        m = self.moods[who]
        if m.why == "reaction" and m.by is not None and m.act in DONE:
            mood = f"You're {m.mood}: {self.label(m.by)} just {DONE[m.act]} you."
        elif m.mood != "neutral":
            mood = f"You're feeling {m.mood}."
        else:
            mood = ""
        return (
            f"How you feel about everyone here right now: {about}. {mood} Let it show in how "
            "you speak to them, without saying how you feel in so many words."
        ).replace("  ", " ")
