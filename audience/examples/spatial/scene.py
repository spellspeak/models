"""A room with people in it, turned into the request SpellSpeak Audience reads.

A scene is what a game knows when the player speaks: where the player and everyone else stand and face, the objects
in the room, the conversation state (who is in the player's group, who follows them, who asked them something, who
spoke with them last), the lines before this one and the player's line. `scene_request` turns it into an
`AddresseeRequest` through the runtime's `bands` function:

- People out of earshot are left out of the request. A game never asks who a line is for among people who cannot hear it.
- A person within `OBJECT_M` of an object gets `near: <phrase>` on their card, replacing any `near` the card had, so
  "the one by the fire" changes meaning when someone walks over to the fire.
- Earlier lines that involve someone out of earshot are dropped.
- `text_only` leaves the spatial facts off every card: the same scene as a game without positions would send it.
"""
from __future__ import annotations

import math

from contracts.schemas.addressee import PLAYER, AddresseeRequest
from harness.addressee.bands import Band, BandConfig, Pose, bands

OBJECT_M = 1.5


def scene_request(scene: dict, cards: dict[str, dict], *, text_only: bool = False,
                  cfg: BandConfig | None = None) -> tuple[AddresseeRequest, dict[str, Band], list[str]]:
    """(the request, the bands for everyone, the ids left out because they cannot hear)."""
    cfg = cfg or BandConfig()
    p = scene["player"]
    poses, specs = {}, {}
    for spec in scene["people"]:
        c = cards[spec["card"]] if isinstance(spec["card"], str) else spec["card"]
        specs[c["id"]] = (c, spec)
        poses[c["id"]] = Pose(float(spec["x"]), float(spec["y"]), float(spec.get("facing", 0.0)))
    group = scene.get("group")
    b = bands(Pose(float(p["x"]), float(p["y"]), float(p.get("facing", 0.0))), poses, cfg,
              group=set(group) if group is not None else None, following=set(scene.get("following") or []),
              asked=set(scene.get("asked") or []), last_spoke=scene.get("last_spoke"))
    present, out = [], []
    for pid, (c, spec) in specs.items():
        if not b[pid].can_hear:
            out.append(pid)
            continue
        feats = [f for f in c.get("features", []) if str(f["key"]).lower() != "near"]
        near = nearest_object(spec, scene.get("objects") or [])
        if near:
            feats.append({"key": "near", "value": near})
        present.append({**c, "features": feats,
                        **({} if text_only else {"spatial": b[pid].spatial.model_dump(exclude_none=True)})})
    keep = {c["id"] for c in present} | {PLAYER}
    history = [h for h in scene.get("history") or [] if h["speaker"] in keep and all(t in keep for t in h.get("to", []))]
    req = AddresseeRequest.model_validate({"text": scene.get("text") or "...", "present": present, "history": history})
    return req, b, out


def nearest_object(spec: dict, objects: list[dict]) -> str | None:
    best, phrase = OBJECT_M, None
    for o in objects:
        d = math.hypot(float(o["x"]) - float(spec["x"]), float(o["y"]) - float(spec["y"]))
        if d <= best:
            best, phrase = d, o["phrase"]
    return phrase
