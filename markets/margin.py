"""Turn bookmaker odds into probabilities.

Decimal odds of 2.50 pay 2.50 per 1 staked, so the "raw" probability is
1/2.50 = 0.40. The three raw probabilities of a match add up to more than 1;
the excess is the bookmaker's margin (the overround). How the margin is taken
back out matters, because bookmakers do not spread it evenly:

- proportional: scale all three down by the same factor.
- power:        raise each to a power k chosen so they sum to 1; takes more
                margin off long shots than off favourites.
- shin:         Shin's (1993) model, in which the bookmaker protects itself
                against a share z of bettors who know the result; it also
                takes more off long shots.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq


def raw(odds: np.ndarray) -> np.ndarray:
    return 1.0 / np.asarray(odds, dtype=float)


def overround(odds: np.ndarray) -> np.ndarray:
    """Margin per match: sum of raw probabilities minus 1 (0.05 = 5%)."""
    return raw(odds).sum(axis=1) - 1.0


def proportional(odds: np.ndarray) -> np.ndarray:
    r = raw(odds)
    return r / r.sum(axis=1, keepdims=True)


def _rows(odds: np.ndarray, solve) -> np.ndarray:
    r = raw(odds)
    out = np.full_like(r, np.nan)
    for i, row in enumerate(r):
        if np.any(row >= 1.0) or np.any(row <= 0.0):
            continue  # decimal odds of 1.0 or less (a "certain" result) can't be a real price: leave NaN
        if np.all(np.isfinite(row)) and row.sum() > 1.0:
            out[i] = solve(row)
        elif np.all(np.isfinite(row)):
            out[i] = row / row.sum()  # no margin to remove
    return out


def power(odds: np.ndarray) -> np.ndarray:
    def solve(row):
        f = lambda k: np.sum(row ** k) - 1.0
        hi = 10.0
        while f(hi) > 0 and hi < 1e4:  # a heavy favourite near 100% needs a larger exponent
            hi *= 4
        if f(hi) > 0:
            return row / row.sum()
        k = brentq(f, 1.0, hi)
        return row ** k
    return _rows(odds, solve)


def shin(odds: np.ndarray) -> np.ndarray:
    """Shin probabilities: p_i = (sqrt(z^2 + 4(1-z) r_i^2 / S) - z) / (2(1-z))."""
    def probs(row, z):
        s = row.sum()
        return (np.sqrt(z * z + 4 * (1 - z) * row ** 2 / s) - z) / (2 * (1 - z))

    def solve(row):
        z = brentq(lambda z: probs(row, z).sum() - 1.0, 0.0, 0.4)
        return probs(row, z)
    return _rows(odds, solve)


METHODS = {"proportional": proportional, "power": power, "shin": shin}
