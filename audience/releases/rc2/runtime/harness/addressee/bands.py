"""Positions to spatial facts: the one piece of harness logic a scene demo needs.

A game knows where everyone stands and which way they face. The addressee model reads plain bands instead
(contracts/schemas/person_card.py `SpatialFacts`), so it is never tied to one game's units. This turns poses
into those bands. Band edges are per game (`BandConfig`); a heatmap of the answers over the floor helps tune them.

Coordinates are any flat 2D frame in metres. Facing is in degrees in the same frame (`atan2(dy, dx)`), so the
handedness of the frame does not matter. The player's facing is read when they start speaking, not when they stop.

The group rule here is a placeholder: an explicit group from the game wins; otherwise a person is in the group
when they stand within `group_m` of the player, in front of them, and face them. Anyone following the player is in
the group. A real game should use its own conversation state.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from contracts.schemas.person_card import SpatialFacts


@dataclass(frozen=True)
class Pose:
    x: float
    y: float
    facing: float = 0.0  # degrees


@dataclass(frozen=True)
class BandConfig:
    near_m: float = 3.0               # conversation distance
    mid_m: float = 8.0                # across a room
    earshot_m: float = 15.0           # beyond this a person cannot hear the line and is left out of the request
    gaze_half_angle_deg: float = 20.0
    group_m: float = 2.5
    group_facing_deg: float = 60.0


@dataclass(frozen=True)
class Band:
    spatial: SpatialFacts
    can_hear: bool
    distance_m: float
    angle_deg: float  # from the player's facing to the person, 0 to 180


def _angle(a: float, b: float) -> float:
    d = (a - b + 180.0) % 360.0 - 180.0
    return abs(d)


def bands(player: Pose, people: dict[str, Pose], cfg: BandConfig = BandConfig(), *, group: set[str] | None = None,
          following: set[str] = frozenset(), asked: set[str] = frozenset(), last_spoke: str | None = None) -> dict[str, Band]:
    out = {}
    for pid, p in people.items():
        dx, dy = p.x - player.x, p.y - player.y
        dist = math.hypot(dx, dy)
        toward = math.degrees(math.atan2(dy, dx)) if dist > 1e-9 else player.facing
        angle = _angle(toward, player.facing)
        distance = "near" if dist <= cfg.near_m else "mid" if dist <= cfg.mid_m else "far"
        if group is not None:
            in_group = pid in group
        else:
            back = math.degrees(math.atan2(-dy, -dx))  # from the person toward the player
            in_group = dist <= cfg.group_m and angle <= 90.0 and _angle(p.facing, back) <= cfg.group_facing_deg
        in_group = in_group or pid in following
        out[pid] = Band(spatial=SpatialFacts(distance=distance, in_view=angle <= cfg.gaze_half_angle_deg, in_group=in_group,
                                             following=pid in following, asked_you=pid in asked,
                                             last_spoke_with_you=pid == last_spoke),
                        can_hear=dist <= cfg.earshot_m, distance_m=round(dist, 3), angle_deg=round(angle, 2))
    return out
