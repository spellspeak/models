"""How SpellSpeak Tone reads a line (input format RENDER_VERSION). Shared by training and the runtime.

Everyone in the scene comes first, as markers, so truncation can only cut the previous line:

    People: [Tomas] [Wren] [the player]. Mara to Tomas: "You still owe me ten coins." Before: Tomas: Lovely day.
"""
from __future__ import annotations

from contracts.schemas.line_tags import PLAYER

RENDER_VERSION = "linecls-input-0.1"


def who(n: str | None) -> str:
    return "the player" if n == PLAYER else (n or "everyone")


def render(inp: dict) -> tuple[str, list[tuple[int, int]]]:
    """The input text and, per target in the caller's order, the character span of its marker (brackets included).

    The addressee's marker always comes first, then the others in the caller's order. Training lines almost always
    listed the addressee first, and the models learned that position (found in an early demo), so the
    runtime renders every line the same way whatever order the harness passes."""
    targets = list(inp["targets"])
    to = inp.get("to")
    order = ([to] + [t for t in targets if t != to]) if to in targets else targets
    text, at = "People:", {}
    for t in order:
        start = len(text) + 1
        text += f" [{who(t)}]"
        at[t] = (start, len(text))
    spans = [at[t] for t in targets]
    text += f". {who(inp['speaker'])} to {who(inp.get('to'))}: \"{inp['text']}\""
    if inp.get("previous"):
        prev = inp["previous"]
        name, sep, rest = prev.partition(":")
        text += f" Before: {who(name.strip()) if sep else ''}{':' if sep else ''}{rest if sep else prev}"
    return text, spans


def span_mask(offsets: list[tuple[int, int]], spans: list[tuple[int, int]]) -> list[list[float]]:
    """Per target, which tokens belong to its marker (special tokens have empty offsets and never do)."""
    rows = []
    for a, b in spans:
        row = [1.0 if (t > s and s >= a and t <= b) else 0.0 for s, t in offsets]
        if not any(row):
            row[0] = 1.0
        rows.append(row)
    return rows
