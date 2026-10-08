"""A heart per character: how they feel about you, 0 to 100, moved by what Tone says you did to them.

This is the small version for the example. Only your lines move hearts, by the act toward each character
and its intensity, when Tone is at least half sure. The framework's feeling meters (trust, affection,
fear, respect and temper, with buffers, hysteresis and a two-hit rule) replace this in a real game.
"""

from __future__ import annotations

from contracts.schemas.line_tags import PLAYER, LineTags

# Points at medium intensity. Hostile acts cost more than kind ones give: a heart is easier to lose than to win.
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
CONFIDENCE = 0.5


class Hearts:
    def __init__(self, names: list[str], start: int = 50):
        self.value: dict[str, int] = {n: start for n in names}

    def on_line(self, speaker: str, tags: LineTags) -> dict[str, int]:
        """Apply one tagged line. Returns the change per character, for the ones that moved."""
        if speaker != PLAYER or tags.backchannel:
            return {}
        changes: dict[str, int] = {}
        for name, tag in tags.acts.items():
            if name not in self.value:
                continue
            if tag.confidence is not None and tag.confidence < CONFIDENCE:
                continue
            delta = round(EFFECTS[tag.act] * INTENSITY[tag.intensity])
            if not delta:
                continue
            before = self.value[name]
            self.value[name] = max(0, min(100, before + delta))
            if self.value[name] != before:
                changes[name] = self.value[name] - before
        return changes
