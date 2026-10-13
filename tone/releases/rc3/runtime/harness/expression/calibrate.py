"""Confidence calibration for SpellSpeak Tone (from revision r7).

The classifier's raw confidences rank lines well but do not mean what they say (r6: act calibration error 0.24; half
of all pairs sat at 0.6 to 0.7 and were right 96% of the time). A calibrated confidence is the chance the tag is right:

- a hostile tag (insult, threat, accusation, or demand at high intensity): the chance the line is hostile toward
  that person;
- any other tag: the chance the act is right;
- the emotion: the chance the emotion is right.

Each is one rising curve (Platt scaling: sigmoid(a * logit(p) + b)) fitted on the dev set
and stored in the model's config.json under `calibration`. Because every curve rises,
the classifier's decisions do not change; only the numbers it reports do, and with them what passes the meters' bar.
"""
from __future__ import annotations

import math

EPS = 1e-6


def logit(p: float) -> float:
    p = min(max(float(p), EPS), 1 - EPS)
    return math.log(p / (1 - p))


def platt(p: float, ab: dict) -> float:
    z = ab["a"] * logit(p) + ab["b"]
    return 1.0 / (1.0 + math.exp(-z)) if z >= 0 else math.exp(z) / (1.0 + math.exp(z))


def tag_confidence(raw: float, hostile: bool, cal: dict | None) -> float:
    """The confidence the runtime reports for an act tag: the raw value when the model has no calibration."""
    if not cal:
        return raw
    return platt(raw, cal["hostility" if hostile else "act"])


def emotion_confidence(raw: float, cal: dict | None) -> float:
    if not cal:
        return raw
    return platt(raw, cal["emotion"])


def exchange_confidence(raw: float, cal: dict | None) -> float:
    """r8: the chance the exchange label is right; the raw top probability when the model has no exchange curve."""
    if not cal or "exchange" not in cal:
        return raw
    return platt(raw, cal["exchange"])


def fit_platt(p, y, l2: float = 1e-3, iters: int = 100) -> dict:
    """Two parameters by Newton's method on the log loss of y (0 or 1) given logit(p); a little L2 for stability."""
    import numpy as np

    x = np.array([logit(v) for v in p], dtype=float)
    y = np.asarray(y, dtype=float)
    a, b = 1.0, 0.0
    for _ in range(iters):
        q = 1.0 / (1.0 + np.exp(-(a * x + b)))
        w = q * (1 - q)
        g = np.array([np.sum((q - y) * x) + l2 * (a - 1.0), np.sum(q - y) + l2 * b])
        h = np.array([[np.sum(w * x * x) + l2, np.sum(w * x)], [np.sum(w * x), np.sum(w) + l2]])
        step = np.linalg.solve(h, g)
        a, b = a - step[0], b - step[1]
        if np.max(np.abs(step)) < 1e-9:
            break
    return {"a": round(float(a), 6), "b": round(float(b), 6), "items": int(len(x))}
