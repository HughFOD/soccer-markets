"""Fair-price engine: combine every bookmaker's odds into one fair price, and flag prices that are out of line.

How a fair price is made
------------------------
1. Each bookmaker's odds are turned into probabilities with the margin removed
   (the power method, which takes more margin off long shots; see margin.py).
2. The bookmakers are combined with a weighted *logarithmic pool*:

       log fair_i  =  sum_b  w_b * log p_{b,i}   + constant,

   then rescaled so home + draw + away = 1. The weights are learned by
   matching Pinnacle's *closing* price (the sharpest price, set just before
   kick-off) from the earlier snapshot of every bookmaker's odds. Learning
   from closing prices rather than results is far less noisy: results are
   mostly luck, closing prices are the market's final, best-informed view.
   Weights come from the previous two seasons only and are refitted each
   season (walk-forward), so a season is never priced with weights that saw it.
3. When some bookmakers are missing for a match, the remaining weights are
   scaled up so they keep the same total.

How a price is flagged
----------------------
A bookmaker's price is flagged when the fair probability times its odds is
above 1 + threshold, i.e. the price pays more than the fair price says it
should. The backtest checks two things for flagged prices:

- Return: the profit per 1 staked. Honest but very noisy.
- Closing-line value (CLV): how the price taken compares with Pinnacle's
  closing price just before kick-off, the sharpest price available. Beating
  the closing price is the standard test of whether a price was really
  generous, and it is far less noisy than profit because it does not depend
  on who won.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from . import efficiency as ef, margin

HDA = ["h", "d", "a"]
MAX_EDGE = 0.25


def books_in(m: pd.DataFrame) -> list[str]:
    return sorted({c.split("_")[1] for c in m.columns if c.startswith("bk_")})


def book_probs(m: pd.DataFrame, books: list[str]) -> np.ndarray:
    """books x matches x 3 array of margin-free probabilities (NaN where a bookmaker had no price)."""
    out = np.full((len(books), len(m), 3), np.nan)
    for j, b in enumerate(books):
        O = m[[f"bk_{b}_{o}" for o in HDA]].to_numpy(float)
        ok = np.isfinite(O).all(1)
        # ignore a price set that cannot be right: chances adding to under 99% or over 120%
        with np.errstate(invalid="ignore", divide="ignore"):
            over = (1 / O).sum(1) - 1
        ok &= (over > -0.01) & (over < 0.20)
        if ok.any():
            out[j, ok] = margin.power(O[ok])
    return out


def pool(L: np.ndarray, w: np.ndarray, total: float | None = None) -> np.ndarray:
    """Weighted log pool. L: books x matches x 3 log-probabilities (NaN = missing)."""
    avail = np.isfinite(L[:, :, 0])                                   # books x matches
    wa = np.where(avail, w[:, None], 0.0)
    s = wa.sum(0)
    total = w.sum() if total is None else total
    scale = np.divide(total, s, out=np.zeros_like(s), where=s > 0)
    z = np.nansum(np.where(avail[:, :, None], L, 0.0) * (wa * scale)[:, :, None], axis=0)
    z -= z.max(1, keepdims=True)
    P = np.exp(z)
    P /= P.sum(1, keepdims=True)
    P[s == 0] = np.nan
    return P


def fit_weights(Pb: np.ndarray, target: np.ndarray, min_rows: int = 50) -> np.ndarray:
    """Weights (one per bookmaker, >= 0) whose pooled price best matches `target` probabilities.

    Parametrised as total * softmax(theta): theta sets each bookmaker's share,
    total how confident the pooled price is. Bookmakers with fewer than
    `min_rows` prices get no weight.
    """
    L = np.log(np.clip(Pb, 1e-9, 1))
    ok = np.isfinite(target).all(1) & np.isfinite(L[:, :, 0]).any(0)
    L, T = L[:, ok], target[ok]
    idx = np.flatnonzero(np.isfinite(L[:, :, 0]).sum(1) >= min_rows)
    if len(idx) == 0:
        return np.zeros(Pb.shape[0])

    def weights(x):
        th = x[:-1]
        sh = np.exp(th - th.max())
        sh /= sh.sum()
        w = np.zeros(L.shape[0])
        w[idx] = np.exp(x[-1]) * sh
        return w

    def loss(x):
        return float(-(T * np.log(np.clip(pool(L, weights(x)), 1e-12, 1))).sum(1).mean())
    return weights(minimize(loss, np.zeros(len(idx) + 1), method="L-BFGS-B").x)


def closing_fair(m: pd.DataFrame) -> np.ndarray:
    """The target: the sharpest closing price available for each match, margin removed.

    Pinnacle's closing price where the data has it; otherwise the Betfair
    Exchange closing price (football-data.co.uk stopped publishing Pinnacle in
    2026/27, and the exchange, where bettors trade with each other, is the
    sharpest price left).
    """
    out = np.full((len(m), 3), np.nan)
    for cols in (["pinc_h", "pinc_d", "pinc_a"], [f"bkc_BFE_{o}" for o in HDA]):
        if set(cols) <= set(m.columns):
            O = m[cols].to_numpy(float)
            ok = ~np.isfinite(out).all(1) & np.isfinite(O).all(1)
            if ok.any():
                out[ok] = margin.power(O[ok])
    return out


def walk_forward(m: pd.DataFrame, books: list[str], train_seasons: int = 2) -> tuple[np.ndarray, pd.DataFrame]:
    """Fair prices for each season from weights fitted on the previous seasons that have closing prices."""
    Pb = book_probs(m, books)
    L = np.log(np.clip(Pb, 1e-9, 1))
    Pc = closing_fair(m)
    has_close = np.isfinite(Pc).all(1)
    close_seasons = sorted(m.loc[has_close, "season"].unique())
    P = np.full((len(m), 3), np.nan)
    rows = []
    for s in sorted(m["season"].unique()):
        prior = [x for x in close_seasons if x < s][-train_seasons:]
        if not prior:
            continue
        tr = m["season"].isin(prior).to_numpy() & has_close
        te = (m["season"] == s).to_numpy()
        w = fit_weights(Pb[:, tr], Pc[tr])
        P[te] = pool(L[:, te], w)
        rows.append({"season": s, "trained_on": " ".join(prior), **{b: float(x) for b, x in zip(books, w)}})
    return P, pd.DataFrame(rows).set_index("season")


def latest_weights(m: pd.DataFrame, books: list[str], train_seasons: int = 2,
                   available: list[str] | None = None) -> dict[str, float]:
    """Weights for pricing upcoming matches, fitted on the most recent seasons with closing prices.

    `available`: the bookmakers that actually price the upcoming matches; the
    weights are fitted with only those, so a bookmaker that has left the data
    does not take weight that the others then have to cover.
    """
    use = [b for b in books if available is None or b in available]
    Pc = closing_fair(m)
    has_close = np.isfinite(Pc).all(1)
    seasons = sorted(m.loc[has_close, "season"].unique())[-train_seasons:]
    tr = m["season"].isin(seasons).to_numpy() & has_close
    w = fit_weights(book_probs(m, use)[:, tr], Pc[tr])
    return {b: float(x) for b, x in zip(use, w) if x > 0}


def edges(m: pd.DataFrame, P: np.ndarray, books: list[str]) -> np.ndarray:
    """books x matches x 3 expected profit per 1 staked at each bookmaker's price, if the fair price is right."""
    E = np.full((len(books), len(m), 3), np.nan)
    for j, b in enumerate(books):
        O = m[[f"bk_{b}_{o}" for o in HDA]].to_numpy(float)
        E[j] = P * O - 1
    return E


def _best_retail(m, P, books):
    """For each match and outcome, the retail bookmaker whose price beats the fair price by the most."""
    from .data import SHARP
    E = edges(m, P, books)
    O = np.stack([m[[f"bk_{b}_{o}" for o in HDA]].to_numpy(float) for b in books])
    for j, b in enumerate(books):
        if b in SHARP:
            E[j] = np.nan
    Eb = np.where(np.isfinite(E), E, -np.inf)
    j = Eb.argmax(0)
    e = np.take_along_axis(Eb, j[None], 0)[0]
    odds = np.take_along_axis(O, j[None], 0)[0]
    e[~np.isfinite(odds)] = -np.inf
    e[e > MAX_EDGE] = -np.inf          # a gap this big is almost always a typo in the data, not a real price
    return e, odds, j


def backtest(m: pd.DataFrame, Y: np.ndarray, P: np.ndarray, books: list[str],
             thresholds=(0.0, 0.01, 0.02, 0.03, 0.05)) -> dict:
    """Score the flags: closing-line value (the main test), share that beat the close, and profit."""
    e, odds, jbest = _best_retail(m, P, books)
    Pc = closing_fair(m)
    priced = np.isfinite(P).all(1) & np.isfinite(Pc).all(1)
    weeks = max(m.loc[priced, "date"].dt.to_period("W").nunique(), 1)

    def score(flag, seed=0):
        clv_num = np.where(flag, odds * Pc - 1, 0).sum(1)
        den = flag.sum(1).astype(float)
        k = den > 0
        clv = ef.ratio_ci(clv_num[k], den[k], seed=seed) if k.any() else (np.nan,) * 3
        r = ef.flat_return(np.where(flag, odds, np.nan), Y, flag, seed=seed)
        return {"bets": int(flag.sum()), "expected": float(e[flag].mean()) if flag.any() else np.nan,
                "clv": clv[0], "clv_lo": clv[1], "clv_hi": clv[2],
                "beat_close": float((odds * Pc > 1)[flag].mean()) if flag.any() else np.nan,
                "return": r["return"], "lo": r["lo"], "hi": r["hi"]}

    rules = []
    for i, t in enumerate(thresholds):
        flag = priced[:, None] & (e > t)
        rules.append({"threshold": t, **score(flag, i), "bets_per_week": float(flag.sum() / weeks)})
    flag2 = priced[:, None] & (e > 0.02)
    by_season = []
    for s, g in m.groupby("season"):
        f = np.zeros_like(flag2)
        f[g.index] = flag2[g.index]
        if f.sum():
            by_season.append({"season": s, **score(f, 3)})
    by_book = []
    for j, b in enumerate(books):
        f = flag2 & (jbest == j)
        if f.sum() >= 20:
            by_book.append({"book": b, **score(f, j)})
    return {"matches": int(priced.sum()), "weeks": int(weeks), "rules": pd.DataFrame(rules),
            "by_season": pd.DataFrame(by_season), "by_book": pd.DataFrame(by_book)}


def accuracy(m: pd.DataFrame, Y: np.ndarray, P: np.ndarray, books: list[str]) -> pd.DataFrame:
    """How close each price is to the closing price (KL divergence) and to the results (log loss)."""
    Pb = book_probs(m, books)
    Pc = closing_fair(m)
    cands = {"Fair price (this engine)": P,
             "Equal-weight average": pool(np.log(np.clip(Pb, 1e-9, 1)), np.ones(len(books)) / len(books), 1.0)}
    for b, name in (("PS", "Pinnacle alone"), ("B365", "Bet365 alone")):
        if b in books:
            cands[name] = Pb[books.index(b)]
    ok = np.isfinite(Pc).all(1)
    for v in cands.values():
        ok &= np.isfinite(v).all(1)
    base_kl = (Pc[ok] * np.log(Pc[ok] / np.clip(P[ok], 1e-12, 1))).sum(1)
    rows = []
    for k, v in cands.items():
        kl = (Pc[ok] * np.log(Pc[ok] / np.clip(v[ok], 1e-12, 1))).sum(1)
        rows.append({"source": k, "matches": int(ok.sum()), "distance_to_close": float(kl.mean()),
                     "vs_fair": float(kl.mean() / base_kl.mean() - 1), "log_loss": float(ef.log_loss(v[ok], Y[ok]).mean())})
    return pd.DataFrame(rows)


def this_week(fx: pd.DataFrame, weights: dict[str, float], threshold: float = 0.02) -> pd.DataFrame:
    """Fair prices for upcoming matches, the best price on offer, and flags."""
    books = [b for b in weights if any(c.startswith(f"bk_{b}_") for c in fx.columns)]
    if not books or fx.empty:
        return pd.DataFrame()
    w = np.array([weights[b] for b in books])
    Pb = book_probs(fx, books)
    P = pool(np.log(np.clip(Pb, 1e-9, 1)), w, total=sum(weights.values()))
    from .data import SHARP
    E = edges(fx, P, books)
    O = np.stack([fx[[f"bk_{b}_{o}" for o in HDA]].to_numpy(float) for b in books])
    O_retail = O.copy()
    for j, b in enumerate(books):
        if b in SHARP:
            O_retail[j] = np.nan
    rows = []
    for i, r in fx.reset_index(drop=True).iterrows():
        if not np.isfinite(P[i]).all():
            continue
        row = {"date": r["date"], "time": r.get("time", ""), "league": r["league"], "home": r["home"], "away": r["away"],
               "n_books": int(np.isfinite(Pb[:, i, 0]).sum())}
        for k, o in enumerate(HDA):
            row[f"fair_{o}"] = P[i, k]
            row[f"fair_odds_{o}"] = 1 / P[i, k]
            col = np.where(np.isfinite(O_retail[:, i, k]), O_retail[:, i, k], -np.inf)
            j = int(col.argmax())
            row[f"best_{o}"] = O[j, i, k] if np.isfinite(O[j, i, k]) else np.nan
            row[f"best_book_{o}"] = books[j]
            row[f"edge_{o}"] = E[j, i, k]
        row["flag"] = ", ".join(f"{lab} @ {row[f'best_{o}']:.2f} ({row[f'best_book_{o}']}, {row[f'edge_{o}']:+.1%})"
                                for o, lab in zip(HDA, ("Home", "Draw", "Away")) if threshold < row[f"edge_{o}"] <= MAX_EDGE)
        rows.append(row)
    return pd.DataFrame(rows)
