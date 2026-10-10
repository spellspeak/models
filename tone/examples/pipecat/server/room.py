"""The room: one conversation between the user and the characters, as it happened.

`Transcript` is who said what, and who each of the user's lines was for. Each character's LLM sees
it from their own seat (`Transcript.view`): their own lines are their replies, everyone else's are
user turns marked with who spoke. Every character is always shown the whole conversation, so
nobody misses what was said while someone else had the floor.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from config import LLM_HISTORY_LINES, Character

USER = "player"  # the user: SpellSpeak Audience's reserved name for the one speaking
NOTE = "note"  # not a speaker: a note in the transcript every character sees, never said

# What a character writes to say nothing at all (never voiced).
SILENT = "[silent]"

# How a line was said: on its own turn, or in a chorus with others.
SAID, TOGETHER = "said", "together"


def normalize(text: str) -> str:
    return " ".join(text.split())


def is_silent(text: str) -> bool:
    return normalize(text).lower().startswith(SILENT)


def could_be_silent(text: str) -> bool:
    """Whether a line still being written might yet turn out to be SILENT."""
    so_far = normalize(text).lower()
    return SILENT.startswith(so_far) or so_far.startswith(SILENT)


def handoff(text: str, cast: Sequence[Character]) -> tuple[str, str | None]:
    """A line as said (its [tags] taken out), and who it hands the floor to: whoever it names in a
    tag ("That's Bruno's department. [to Bruno]"), or, with no tag, whoever it opens by calling
    by name ("Bruno, go easy on them")."""
    spoken = normalize(re.sub(r"\[[^\]]*\]?", " ", text))
    tag = re.search(r"\[\s*to\s+([^\]]+?)\s*\]", text, re.IGNORECASE)
    if tag is not None:
        name = tag.group(1).strip().lower()
        return spoken, next((c.id for c in cast if name in (c.id, c.name.lower())), None)
    # No tag, but the line opens by calling someone by name ("Bruno, they're after a deal…"):
    # it's for them all the same.
    called = re.match(r"\s*(?:hey|oi|right|okay|ok)?[\s,]*(\w+)\s*[,!?—–-]", spoken, re.IGNORECASE)
    if called is not None:
        name = called.group(1).lower()
        return spoken, next((c.id for c in cast if name in (c.id, c.name.lower())), None)
    return spoken, None


def names(labels: Sequence[str]) -> str:
    """'Nova', 'Nova and Bruno', 'Nova, Bruno and Kai'."""
    if len(labels) <= 1:
        return "".join(labels)
    return f"{', '.join(labels[:-1])} and {labels[-1]}"


@dataclass(eq=False)
class Line:
    speaker: str  # USER, NOTE or a character id
    text: str
    interrupted: bool = False
    how: str = SAID
    chorus: int | None = None  # the lines of one chorus share this
    to: list[str] = field(default_factory=list)  # who it was for: ids, or [USER]; [] unclear

    @property
    def by_character(self) -> bool:
        return self.speaker not in (USER, NOTE)


class Transcript:
    """Who said what, in order, and how each character sees it."""

    def __init__(self, cast: Sequence[Character]) -> None:
        self.cast = {c.id: c for c in cast}
        self.lines: list[Line] = []

    def add(
        self,
        speaker: str,
        text: str,
        *,
        interrupted: bool = False,
        how: str = SAID,
        chorus: int | None = None,
        to: Sequence[str] = (),
    ) -> Line:
        line = Line(speaker, normalize(text), interrupted, how, chorus, list(to))
        self.lines.append(line)
        return line

    def remove(self, line: Line) -> None:
        """A line written but never heard (the user cut in first) is taken back out."""
        if line in self.lines:
            self.lines.remove(line)

    def label(self, speaker: str) -> str:
        if speaker == USER:
            return "User"
        if speaker == NOTE:
            return "Note"
        return self.cast[speaker].name

    def view(
        self, me: str, note: str | None = None, limit: int = LLM_HISTORY_LINES
    ) -> list[dict[str, str]]:
        """The conversation as `me`'s LLM sees it (its last `limit` lines): their own lines as
        assistant turns, everyone else's as user turns marked `[User]` or `[Name]`, and the
        moment's note last."""
        messages: list[dict[str, str]] = []

        def say(role: str, content: str) -> None:
            if messages and messages[-1]["role"] == role:
                messages[-1]["content"] += "\n" + content
            else:
                messages.append({"role": role, "content": content})

        for line in self.lines[-limit:]:
            if line.speaker == NOTE:
                say("user", f"[Note: {line.text}]")
            elif line.speaker == me:
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


# What a character is told about the moment, appended to its view as a `[Note: …]` line. A group
# in turn is told who was asked and who has already answered, so nobody answers for the rest.
NOTE_SWITCH = "The person wants your answer now, not {other}'s."
# Asked one at a time, each sees the replies so far in the conversation itself: the note doesn't
# say who has answered, since anyone before them may have stayed out of it.
NOTE_IN_TURN = (
    "The person said that to {who}, and you're answering one at a time; any replies so far are "
    "above. If it asks each of you something, give your own answer in one short sentence. If it's "
    "a question only one person here should take, answer it only if you're the best placed of "
    "everyone here (you know best: {topics}). If someone else here knows it better than you, or "
    f"someone above has already answered it, write only {SILENT}: don't point the person to "
    "them, they'll answer for themselves."
)

# Said at once, so kept to a few words: four people introducing themselves over each other is noise.
NOTE_CHORUS = (
    "The person said that to everyone, and everyone is answering at once, out loud. Keep it very "
    "short, six words at most, in character: a quick 'Hey.', 'Evening.', or your own answer in a "
    "few words. Don't introduce yourself or explain who you are. If it's a question about "
    "what you know best ({topics}), answer it; only if it's plainly someone else's area and not "
    f"yours at all, write only {SILENT}."
)
NOTE_WHO_ME = (
    "The person said that, but it isn't clear who to: it could have been you, or someone else "
    "here, and everyone it might have been for is reacting at once. Just check, in character and "
    "in six words at most, whether they meant you, like 'Who, me?' or 'You talking to me?'. "
    "Nothing else: don't answer it, introduce yourself or take it personally."
)
NOTE_HANDOFF = (
    "{other} just passed that to you, from the person. It's yours: answer in a sentence or two, "
    "to the person (or to {other}, if they asked you something)."
)
NOTE_CARRY_ON = "Carry on."
NOTE_JOINED = "The person walks into the garage."
