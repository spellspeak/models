"""The operating point (plan §5), shared by the runtime, the export check and the scorecard so they never disagree.

A pair is hostile exactly when its hostility probability reaches tau. Then the act is the most likely hostile class
(or a demand, at high intensity, when demand is the top class). Otherwise it is the most likely non-hostile class, and
a demand is held below high intensity. So the tags the meters receive are hostile exactly when the scorecard says so.
"""
from __future__ import annotations

from contracts.schemas.line_tags import ACTS, HOSTILE_ACTS


def decide(pa, p_host: float, tau: float, intensity: str) -> tuple[str, str]:
    """pa: probabilities over ACTS; intensity: the intensity head's top class. Returns (act, intensity)."""
    order = sorted(range(len(ACTS)), key=lambda i: -float(pa[i]))
    if p_host >= tau:
        if ACTS[order[0]] == "demand":
            return "demand", "high"
        act = next(ACTS[i] for i in order if ACTS[i] in HOSTILE_ACTS)
        return act, intensity
    act = next(ACTS[i] for i in order if ACTS[i] not in HOSTILE_ACTS)
    if act == "demand" and intensity == "high":
        intensity = "medium"
    return act, "low" if act == "none" else intensity


def summed_hostility(pa) -> float:
    """For models without a hostility head: the probability mass on the hostile classes."""
    return float(sum(float(pa[ACTS.index(a)]) for a in HOSTILE_ACTS))
