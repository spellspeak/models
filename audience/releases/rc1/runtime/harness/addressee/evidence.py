"""The rules of evidence as code: who a line is for, given what its words pick out and what the game knows.

Two callers: the data generator, which knows by construction what the words of a line pick out and asks for the
label, and the rules baseline (harness/addressee/rules.py), which guesses what the words pick out from the text.
Both then go through `resolve`, so a constructed label and the baseline's answer follow the same rules.

The rules, strongest first:

1. One person present: the line is for them.
2. Words for the whole group ("right, listen to me"): everyone in the player's group when the facts say who that
   is, otherwise everyone present.
3. Words that pick out people: one person, or a set named on purpose ("you two", "Tomas and Wren"), is clear. A
   description that fits several people is broken only by the other evidence agreeing on one of them; else vague
   among those it fits.
4. Words that pick out no one ("You lied to me.", "Yes."): a bare answer goes to whoever asked. Otherwise the other signals
   must agree: who the player was talking with, the one person near and in view, the one person in the group, the
   one person near (or, with nobody near, the one person at mid range). Agreement on one person is clear.
   Disagreement is vague among them. No signal is vague among everyone not known to be far away.
5. A simple, harmless line with no name or description (a greeting, small talk, a simple question, a thank-you).
   After a bare answer: a line that carries on the conversation (a reply, a thank-you, a goodbye, a follow-up) goes to
   the one the player was talking with. Otherwise (an opener: "Hello.", "Who are you?"): the person the player is
   looking at within mid range (the nearest of them), else the one the player was talking with, else the one person
   in the group, else the one person near (or at mid range), else the whole group. Never vague: nobody says
   "Who, me?" to a hello. Someone far away in view is not "looked at".
"""
from __future__ import annotations

from dataclasses import dataclass

from contracts.schemas.addressee import PLAYER, AddresseeLabel, AddresseeRequest
from contracts.schemas.person_card import PersonCard


@dataclass(frozen=True)
class Evidence:
    """What the words and the conversation say, before the spatial facts are read."""

    words: frozenset[str] = frozenset()   # ids the words pick out; empty: the words pick out no one
    words_set: bool = False                # the words name all of `words` on purpose ("you two", "Tomas and Wren")
    words_group: bool = False              # the words are for the whole group ("listen to me", "evening, all")
    asker: str | None = None               # who has a question waiting for the player's answer
    partner: str | None = None             # who the player was talking with
    benign: bool = False                   # a simple, harmless line: greeting, small talk, simple question (rule 5)
    follows: bool = False                  # it carries on the conversation (a reply, thanks, a follow-up), not an opener


def _f(c: PersonCard, name: str):
    return getattr(c.spatial, name) if c.spatial is not None else None


def history_signals(req: AddresseeRequest) -> tuple[str | None, str | None]:
    """(asker, partner) from the history text and the facts. The last line decides: an NPC's question to the player
    makes them the asker; any line between the player and exactly one person makes that person the partner. A fact
    on exactly one card (asked_you, last_spoke_with_you) counts the same when the history says nothing."""
    asker = partner = None
    if req.history:
        last = req.history[-1]
        if last.speaker != PLAYER and (last.to == [PLAYER] or (not last.to and len(req.present) == 1)):
            partner = last.speaker
            if last.text.rstrip().rstrip('"\'').endswith("?"):
                asker = last.speaker
        elif last.speaker == PLAYER and len(last.to) == 1:
            partner = last.to[0]
    if asker is None:
        asked = [c.id for c in req.present if _f(c, "asked_you") is True]
        asker = asked[0] if len(asked) == 1 else None
    if partner is None:
        spoke = [c.id for c in req.present if _f(c, "last_spoke_with_you") is True]
        partner = spoke[0] if len(spoke) == 1 else None
    return asker, partner


def _one(ids: list[str]) -> str | None:
    return ids[0] if len(ids) == 1 else None


def spatial_signals(req: AddresseeRequest, among: list[str] | None = None) -> dict[str, str | None]:
    """The one person each spatial signal points to, or None. `among` limits the people considered."""
    cards = [c for c in req.present if among is None or c.id in among]
    near = [c.id for c in cards if _f(c, "distance") == "near"]
    mid = [c.id for c in cards if _f(c, "distance") == "mid"]
    return {
        "gaze": _one([c.id for c in cards if _f(c, "in_view") is True and (among is not None or _f(c, "distance") == "near")]),
        "group": _one([c.id for c in cards if _f(c, "in_group") is True]),
        # A line said to no one in particular could be for anyone, unless only one person is within a moderate radius.
        "nearby": _one(near) if near else _one(mid),
    }


def _ordered(req: AddresseeRequest, ids) -> list[str]:
    ids = set(ids)
    return [c.id for c in req.present if c.id in ids]


def _agree(req: AddresseeRequest, signals: list[str | None], fallback: list[str]) -> AddresseeLabel:
    pointed = _ordered(req, {s for s in signals if s is not None})
    if len(pointed) == 1:
        return AddresseeLabel(addressed=pointed)
    if len(pointed) >= 2:
        return AddresseeLabel(addressed=pointed, vague=True)
    return AddresseeLabel(addressed=fallback, vague=True) if len(fallback) >= 2 else AddresseeLabel(addressed=fallback)


def resolve(req: AddresseeRequest, ev: Evidence) -> AddresseeLabel:
    ids = req.ids
    if len(ids) == 1:                                                     # rule 1
        return AddresseeLabel(addressed=ids, group=ev.words_group)
    if ev.words_group:                                                    # rule 2
        grouped = [c.id for c in req.present if _f(c, "in_group") is True]
        return AddresseeLabel(addressed=grouped or ids, group=True)
    words = _ordered(req, ev.words)
    if len(words) == 1 or (words and ev.words_set):                       # rule 3, clear
        return AddresseeLabel(addressed=words)
    asker, partner = history_signals(req)
    if words:                                                             # rule 3, a description that fits several
        sp = spatial_signals(req, among=words)
        inside = [s if s in words else None for s in (asker, partner, sp["gaze"], sp["group"])]
        return _agree(req, inside, words)
    if asker is not None:                                                 # rule 4, a bare answer
        return AddresseeLabel(addressed=[asker])
    sp = spatial_signals(req)
    if ev.benign:                                                         # rule 5, a simple harmless line
        if ev.follows and partner is not None:
            return AddresseeLabel(addressed=[partner])
        rank = {"near": 0, "mid": 1, None: 2}
        looked = [c for c in req.present if _f(c, "in_view") is True and _f(c, "distance") != "far"]
        if looked:
            best = min(rank[_f(c, "distance")] for c in looked)
            nearest = [c.id for c in looked if rank[_f(c, "distance")] == best]
            if len(nearest) == 1:
                return AddresseeLabel(addressed=nearest)
        for who in (partner, sp["group"], sp["nearby"]):
            if who is not None:
                return AddresseeLabel(addressed=[who])
        grouped = [c.id for c in req.present if _f(c, "in_group") is True]
        return AddresseeLabel(addressed=grouped or ids, group=True)
    not_far = [c.id for c in req.present if _f(c, "distance") != "far"]
    return _agree(req, [partner, sp["gaze"], sp["group"], sp["nearby"]], not_far if len(not_far) >= 2 else ids)
