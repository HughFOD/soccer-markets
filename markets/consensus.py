"""Compare each site with the consensus of the others.

Consensus price: every site's odds turned into chances (margin removed), then
averaged with equal weight (a logarithmic average, so the three chances still
add up to 100%). No site counts more than another.

Historical test (European bookmakers, 2019/20 onward, the seasons whose files
include each bookmaker's closing odds): when a bookmaker's price beat the
consensus by more than a threshold, did it also beat the consensus *closing*
price, the average of all bookmakers just before kick-off? Betting exchanges
and Pinnacle are left out of both, so the test uses ordinary bookmakers only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import efficiency as ef, margin
from .data import SHARP
from .fairprice import MAX_EDGE, pool

HDA = ["h", "d", "a"]


def _probs(O: np.ndarray) -> np.ndarray:
    out = np.full(O.shape, np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        over = (1 / O).sum(1) - 1
    ok = np.isfinite(O).all(1) & (over > -0.01) & (over < 0.20)
    if ok.any():
        out[ok] = margin.power(O[ok])
    return out


def consensus(stack: np.ndarray, min_sites: int = 3) -> np.ndarray:
    """stack: sites x matches x 3 decimal odds (NaN = no price). Equal-weight consensus chances."""
    P = np.stack([_probs(O) for O in stack])
    L = np.log(np.clip(P, 1e-9, 1))
    n = np.isfinite(P[:, :, 0]).sum(0)
    C = pool(L, np.ones(len(stack)) / len(stack), 1.0)
    C[n < min_sites] = np.nan
    return C


def retail_books(m: pd.DataFrame, closing: bool = False) -> list[str]:
    pre = "bkc_" if closing else "bk_"
    return sorted({c.split("_")[1] for c in m.columns if c.startswith(pre)} - set(SHARP))


def backtest(m: pd.DataFrame, Y: np.ndarray, thresholds=(0.0, 0.01, 0.02, 0.03, 0.05)) -> dict:
    books = [b for b in retail_books(m, closing=True) if b in retail_books(m)]
    Oo = np.stack([m[[f"bk_{b}_{o}" for o in HDA]].to_numpy(float) for b in books])
    Oc = np.stack([m[[f"bkc_{b}_{o}" for o in HDA]].to_numpy(float) for b in books])
    C_open, C_close = consensus(Oo), consensus(Oc)
    E = C_open[None] * Oo - 1            # each bookmaker against the consensus of all of them
    Eb = np.where(np.isfinite(E), E, -np.inf)
    j = Eb.argmax(0)
    e = np.take_along_axis(Eb, j[None], 0)[0]
    odds = np.take_along_axis(Oo, j[None], 0)[0]
    e[(e > MAX_EDGE) | ~np.isfinite(odds)] = -np.inf
    ok = (np.isfinite(C_open).all(1) & np.isfinite(C_close).all(1))
    rows = []
    for t in thresholds:
        f = ok[:, None] & (e > t)
        num = np.where(f, odds * C_close - 1, 0).sum(1)
        den = f.sum(1).astype(float)
        k = den > 0
        c = ef.ratio_ci(num[k], den[k], seed=int(t * 100)) if k.any() else (np.nan,) * 3
        r = ef.flat_return(np.where(f, odds, np.nan), Y, f, seed=1)
        rows.append({"threshold": t, "bets": int(f.sum()), "expected": float(e[f].mean()) if f.any() else np.nan,
                     "edge_vs_close": c[0], "lo": c[1], "hi": c[2], "beat_close": float((odds * C_close > 1)[f].mean()) if f.any() else np.nan,
                     "return": r["return"], "ret_lo": r["lo"], "ret_hi": r["hi"]})
    seasons = sorted(m.loc[ok, "season"].unique())
    return {"matches": int(ok.sum()), "seasons": seasons, "books": books, "rules": pd.DataFrame(rows)}
