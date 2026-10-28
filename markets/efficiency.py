"""Tests of whether betting odds are efficient forecasts.

An efficient market's probabilities are calibrated (events priced at 30%
happen 30% of the time) and no simple rule makes money after the margin.
Every estimate here comes with a bootstrap confidence interval that
resamples whole matches, because the three outcomes of one match are not
independent.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

EPS = 1e-12


# ---------- scores ----------

def log_loss(P: np.ndarray, Y: np.ndarray) -> np.ndarray:
    """Per-match log loss: -log(probability given to what happened)."""
    return -np.log(np.clip((P * Y).sum(axis=1), EPS, 1))


def brier(P: np.ndarray, Y: np.ndarray) -> np.ndarray:
    return ((P - Y) ** 2).sum(axis=1)


def rps(P: np.ndarray, Y: np.ndarray) -> np.ndarray:
    """Ranked probability score: respects the order H > D > A (a draw is 'closer' to a home win than an away win is)."""
    cp, cy = np.cumsum(P, axis=1)[:, :2], np.cumsum(Y, axis=1)[:, :2]
    return ((cp - cy) ** 2).sum(axis=1) / 2


# ---------- bootstrap ----------

def ratio_ci(num: np.ndarray, den: np.ndarray, n_boot: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    """sum(num)/sum(den) with a 95% interval from resampling matches (rows)."""
    num, den = np.asarray(num, float), np.asarray(den, float)
    est = num.sum() / den.sum() if den.sum() else np.nan
    if len(num) < 2 or not den.sum():
        return est, np.nan, np.nan
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(num), size=(n_boot, len(num)))
    with np.errstate(invalid="ignore", divide="ignore"):
        boots = num[idx].sum(axis=1) / den[idx].sum(axis=1)
    lo, hi = np.nanpercentile(boots, [2.5, 97.5])
    return float(est), float(lo), float(hi)


def mean_ci(x: np.ndarray, n_boot: int = 2000, seed: int = 0):
    return ratio_ci(x, np.ones_like(np.asarray(x, float)), n_boot, seed)


# ---------- calibration ----------

def calibration_table(P: np.ndarray, Y: np.ndarray, n_bins: int = 12) -> pd.DataFrame:
    """Pool all outcomes; bin by priced probability; compare with how often they happened."""
    p, y = P.ravel(), Y.ravel()
    match = np.repeat(np.arange(len(P)), P.shape[1])
    edges = np.unique(np.quantile(p, np.linspace(0, 1, n_bins + 1)))
    b = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, len(edges) - 2)
    rows = []
    for k in range(len(edges) - 1):
        s = b == k
        # per-match sums keep the bootstrap honest about within-match dependence
        num = np.bincount(match[s], weights=y[s], minlength=len(P))
        den = np.bincount(match[s], minlength=len(P)).astype(float)
        keep = den > 0
        f, lo, hi = ratio_ci(num[keep], den[keep], n_boot=1000, seed=k)
        rows.append({"priced": p[s].mean(), "happened": f, "lo": lo, "hi": hi, "n": int(s.sum())})
    return pd.DataFrame(rows)


def calibration_slope(P: np.ndarray, Y: np.ndarray, n_boot: int = 500, seed: int = 0) -> dict:
    """Fit happened ~ logistic(a + b * logit(priced)).

    b = 1: calibrated. b > 1: the market is not confident enough, so favourites
    win more often than priced and long shots less often (the favourite-long-shot bias).
    """
    from scipy.optimize import minimize

    def fit(p, y):
        x = np.log(p / (1 - p))

        def nll(t):
            z = t[0] + t[1] * x
            return np.sum(np.logaddexp(0, z) - y * z)

        def grad(t):
            q = 1 / (1 + np.exp(-(t[0] + t[1] * x)))
            return np.array([np.sum(q - y), np.sum((q - y) * x)])
        return minimize(nll, [0.0, 1.0], jac=grad, method="BFGS").x

    p = np.clip(P, 1e-6, 1 - 1e-6)
    a, b = fit(p.ravel(), Y.ravel())
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(n_boot):
        i = rng.integers(0, len(P), len(P))
        bs.append(fit(p[i].ravel(), Y[i].ravel())[1])
    lo, hi = np.percentile(bs, [2.5, 97.5])
    return {"intercept": float(a), "slope": float(b), "slope_lo": float(lo), "slope_hi": float(hi)}


# ---------- returns ----------

ODDS_BINS = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 7.0, 10.0, 1000.0)


def returns_by_odds(odds: np.ndarray, Y: np.ndarray, bins=ODDS_BINS) -> pd.DataFrame:
    """Average profit per 1 staked on every outcome whose odds fall in each band."""
    o, y = odds.ravel(), Y.ravel()
    match = np.repeat(np.arange(len(odds)), odds.shape[1])
    ok = np.isfinite(o)
    rows = []
    for lo_b, hi_b in zip(bins[:-1], bins[1:]):
        s = ok & (o >= lo_b) & (o < hi_b)
        if s.sum() < 30:
            continue
        num = np.bincount(match[s], weights=(o[s] * y[s] - 1), minlength=len(odds))
        den = np.bincount(match[s], minlength=len(odds)).astype(float)
        keep = den > 0
        r, lo, hi = ratio_ci(num[keep], den[keep], n_boot=1000, seed=int(lo_b * 10))
        label = f"{lo_b:g}–{hi_b:g}" if hi_b < 1000 else f"{lo_b:g}+"
        rows.append({"odds": label, "lo_odds": lo_b, "return": r, "lo": lo, "hi": hi, "bets": int(s.sum()),
                     "win_rate": float(y[s].mean())})
    return pd.DataFrame(rows)


def flat_return(odds: np.ndarray, Y: np.ndarray, mask: np.ndarray | None = None, seed: int = 0):
    """Profit per 1 staked when betting 1 on every outcome in `mask` (default: all)."""
    mask = np.isfinite(odds) if mask is None else (mask & np.isfinite(odds))
    num = np.where(mask, odds * Y - 1, 0).sum(axis=1)
    den = mask.sum(axis=1).astype(float)
    keep = den > 0
    est, lo, hi = ratio_ci(num[keep], den[keep], seed=seed)
    return {"return": est, "lo": lo, "hi": hi, "bets": int(den.sum())}


# ---------- opening vs closing ----------

def line_moves(p_open: np.ndarray, p_close: np.ndarray, odds_open: np.ndarray, Y: np.ndarray,
               thresholds=(0.01, 0.02, 0.03, 0.05)) -> pd.DataFrame:
    """If the price moves before kick-off, did the move point the right way?

    For outcomes whose probability rose by at least t between the opening and
    closing odds, the return from having bet at the opening odds. A positive
    number means late information (team news, injuries, informed money) was
    real and the opening price had not yet absorbed it.
    """
    move = p_close - p_open
    rows = []
    for t in thresholds:
        for direction, mask in (("shortened", move >= t), ("drifted", move <= -t)):
            r = flat_return(odds_open, Y, mask, seed=int(t * 1000))
            rows.append({"threshold": t, "direction": direction, **r})
    return pd.DataFrame(rows)
