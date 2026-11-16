"""Margin and de-vig helpers shared across bookmaker comparisons.

These helpers are only valid for a set of outcomes that is mutually exclusive
AND exhaustive (exactly one outcome wins), e.g. 1X2, one Over/Under line,
BTTS, or one 2-way handicap line. They are NOT valid for double chance or
1X2 1UP/2UP markets: their outcomes overlap, so the implied probabilities
legitimately sum to more than 1 and margin / de-vig values are meaningless.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import isfinite, sqrt


def _implied(odds: Sequence[float | None]) -> list[float] | None:
    """Return 1/odds per outcome, or None if the odds are unusable.

    Unusable means fewer than two outcomes, or any odds that are None,
    NaN, infinite or <= 1.0.
    """
    if len(odds) < 2:
        return None
    if any(o is None or not isfinite(o) or o <= 1.0 for o in odds):
        return None
    return [1.0 / o for o in odds]  # type: ignore[operator]


def margin(odds: Sequence[float]) -> float | None:
    """Overround: sum of implied probabilities minus 1.

    Only meaningful for mutually exclusive and exhaustive outcomes; not for
    double chance or 1X2 1UP/2UP (overlapping outcomes).
    """
    implied = _implied(odds)
    return None if implied is None else sum(implied) - 1.0


def devig_multiplicative(odds: Sequence[float]) -> list[float] | None:
    """Remove the margin by proportional normalisation.

    Only valid for mutually exclusive and exhaustive outcomes; not for double
    chance or 1X2 1UP/2UP (overlapping outcomes).
    """
    implied = _implied(odds)
    if implied is None:
        return None
    total = sum(implied)
    return [p / total for p in implied]


def devig_shin(odds: Sequence[float], tol: float = 1e-12) -> list[float] | None:
    """Remove the margin with Shin's insider-trading model.

    p_i(z) = (sqrt(z^2 + 4(1-z) pi_i^2 / Pi) - z) / (2(1-z)), with z found
    by bisection on [0, 0.5) so that sum(p_i) = 1. If Pi <= 1 there is no
    margin to remove and the normalised implied probabilities are returned.
    Returns None if the bisection does not converge (e.g. margin too large
    for a solution with z < 0.5). Only valid for mutually exclusive and
    exhaustive outcomes; not for double chance or 1X2 1UP/2UP.
    """
    implied = _implied(odds)
    if implied is None:
        return None
    total = sum(implied)
    if total <= 1.0:
        return [p / total for p in implied]

    def probs(z: float) -> list[float]:
        return [
            (sqrt(z * z + 4.0 * (1.0 - z) * p * p / total) - z)
            / (2.0 * (1.0 - z))
            for p in implied
        ]

    lo, hi = 0.0, 0.5
    for _ in range(200):
        mid = (lo + hi) / 2.0
        gap = sum(probs(mid)) - 1.0
        if abs(gap) < tol:
            break
        # sum(p) falls as z rises: too high means z must increase.
        if gap > 0:
            lo = mid
        else:
            hi = mid
    if abs(sum(probs(mid)) - 1.0) > 1e-9:
        return None
    return probs(mid)
