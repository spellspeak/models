"""Inputs for the cached-cards addressee model (`TT_VERSION`). Shared by training and the runtime.

The single-pass model reads every card with every line (harness/addressee/render.py), which cost 18 to 65 ms on our
test Mac for one to eight people. This model splits the work:

- A card's text, without its spatial facts, is encoded once and cached. It changes only when what the player can see
  of that person changes (an item picked up, a hood raised, walking over to the fire).
- The player's line is encoded on every utterance, with the line before it as context: a few dozen tokens.
- The spatial facts and the conversation state become a small vector per person, so moving people around never
  re-encodes anything.

Per-person vector (PERSON_DIM): distance near, mid, far, unknown; in view yes, no, unknown; in group yes, no, unknown;
following; asked you (fact); spoke with you last (fact); the last history line was theirs to the player; it was a
question; the player's last line was to them; they spoke at all in the history; the player spoke to them at all;
one over the number of people present; then the rules baseline's word matcher and answer: their name or alias used
to call them, only mentioned, their best feature match (share of three words), they have the top match, pointed at by
who they are with, the rules' probability for them.
Line vector (LINE_DIM): number of people present (one-hot, 1 to 8), any spatial fact known, any history; group words,
pair words ("you two"), the rules call the line unclear, the rules call it a group line; a simple harmless line and an
opener by the word lists (rule 5 in harness/addressee/evidence.py).
"""
from __future__ import annotations

from contracts.schemas.addressee import PLAYER, AddresseeRequest
from contracts.schemas.person_card import PersonCard
from harness.addressee.render import card_text

TT_VERSION = "addressee-tt-0.5"
PERSON_DIM = 25
LINE_DIM = 16


def card_only(c: PersonCard) -> str:
    """The cached part of a card: what the player can see, without where the person is."""
    return card_text(c.without_spatial())


def line_input(req: AddresseeRequest) -> tuple[str, int]:
    """The text the line encoder reads and the character length of the current line within it. Names of earlier
    speakers are left out: who said what is in the per-person vector, so a name in the history is never mistaken for
    a name in the line."""
    cur = f"\"{req.text}\""
    if req.history:
        return cur + f" Before: \"{req.history[-1].text}\"", len(cur)
    return cur, len(cur)


def _three(v: bool | None) -> list[float]:
    return [1.0 if v is True else 0.0, 1.0 if v is False else 0.0, 1.0 if v is None else 0.0]


def person_features(req: AddresseeRequest) -> list[list[float]]:
    from harness.addressee.rules import match_signals, rules_answer

    per, _ = match_signals(req)
    rules = rules_answer(req).addressed
    last = req.history[-1] if req.history else None
    player_last = next((h for h in reversed(req.history) if h.speaker == PLAYER), None)
    n = len(req.present)
    out = []
    for c in req.present:
        s = c.spatial
        d = s.distance if s else None
        v = [1.0 if d == "near" else 0.0, 1.0 if d == "mid" else 0.0, 1.0 if d == "far" else 0.0, 1.0 if d is None else 0.0]
        v += _three(s.in_view if s else None) + _three(s.in_group if s else None)
        v += [float(bool(s and s.following)), float(bool(s and s.asked_you)), float(bool(s and s.last_spoke_with_you))]
        theirs = last is not None and last.speaker == c.id and (PLAYER in last.to or not last.to)
        v += [float(theirs), float(theirs and last.text.rstrip().rstrip('"\'').endswith("?")),
              float(player_last is not None and player_last.to == [c.id]),
              float(any(h.speaker == c.id for h in req.history)),
              float(any(h.speaker == PLAYER and c.id in h.to for h in req.history)),
              1.0 / n]
        v += [*per[len(out)], rules[c.id]]
        out.append(v)
    return out


def line_features(req: AddresseeRequest) -> list[float]:
    from harness.addressee.rules import match_signals, rules_answer

    n = min(len(req.present), 8)
    _, (group_words, pair_words, simple, opener) = match_signals(req)
    ra = rules_answer(req)
    return [1.0 if i == n else 0.0 for i in range(1, 9)] + [float(req.has_spatial), float(bool(req.history)),
                                                           group_words, pair_words, ra.unclear, ra.to_group, simple, opener]
