"""Three further questions about where the market is (in)efficient.

1. Sharp vs soft. Pinnacle takes large bets and keeps a small margin, so its
   price is moved by informed money. Retail ("soft") bookmakers take small
   bets and keep a large margin. Is Pinnacle's price the better forecast, and
   can it be used to find soft-bookmaker prices that are too generous?
2. Over time. As margins shrank, did the market also become better calibrated?
3. By league. Is the less-watched Championship priced less efficiently than
   the Premier League?
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import efficiency as ef, margin

HDA = ["h", "d", "a"]


def cols(prefix: str) -> list[str]:
    return [f"{prefix}_{o}" for o in HDA]


def _lg(P):
    return np.log(np.clip(P, 1e-9, 1))


def sharp_vs_soft(m: pd.DataFrame, Y: np.ndarray, stack) -> dict | None:
    """Accuracy of Pinnacle vs the average bookmaker, and whether the average adds anything to Pinnacle."""
    s = m[cols("pin")].notna().all(1).to_numpy() & m[cols("avg")].notna().all(1).to_numpy()
    if s.sum() < 1000:
        return None
    sub, Ys = m[s].reset_index(drop=True), Y[s]
    Ppin = margin.power(sub[cols("pin")].to_numpy())
    Pavg = margin.power(sub[cols("avg")].to_numpy())
    ok = np.isfinite(Ppin).all(1) & np.isfinite(Pavg).all(1)
    sub, Ys, Ppin, Pavg = sub[ok].reset_index(drop=True), Ys[ok], Ppin[ok], Pavg[ok]
    diff = ef.mean_ci(ef.log_loss(Pavg, Ys) - ef.log_loss(Ppin, Ys))
    P_pin_only = stack(sub["season"], _lg(Ppin), Ys)
    P_both = stack(sub["season"], np.hstack([_lg(Ppin), _lg(Pavg)]), Ys)
    ev = np.isfinite(P_both).all(1) & np.isfinite(P_pin_only).all(1)
    add = ef.mean_ci(ef.log_loss(P_pin_only[ev], Ys[ev]) - ef.log_loss(P_both[ev], Ys[ev]))
    return {"matches": int(len(sub)), "log_loss_pinnacle": float(ef.log_loss(Ppin, Ys).mean()),
            "log_loss_average": float(ef.log_loss(Pavg, Ys).mean()), "average_minus_pinnacle": diff,
            "stack_matches": int(ev.sum()), "gain_from_adding_average": add,
            "margin_pinnacle": float(np.median(margin.overround(sub[cols("pin")].to_numpy()))),
            "margin_average": float(np.median(margin.overround(sub[cols("avg")].to_numpy())))}


def soft_vs_sharp_bets(m: pd.DataFrame, Y: np.ndarray, edges=(0.0, 0.02, 0.04, 0.06, 0.08)) -> dict | None:
    """Bet at the best retail price when it beats Pinnacle's fair price by more than `edge`.

    Pinnacle's fair probability comes from its odds in the same snapshot as the
    retail odds (not its closing odds, which would not have been known yet).
    """
    s = m[cols("pin")].notna().all(1).to_numpy() & m[cols("soft")].notna().all(1).to_numpy()
    if s.sum() < 1000:
        return None
    sub, Ys = m[s].reset_index(drop=True), Y[s]
    fair = margin.power(sub[cols("pin")].to_numpy())
    O = sub[cols("soft")].to_numpy()
    ev = fair * O - 1
    rows = []
    for e in edges:
        mask = np.isfinite(ev) & (ev > e)
        r = ef.flat_return(O, Ys, mask, seed=int(e * 100))
        rows.append({"edge": e, **r, "expected": float(ev[mask].mean()) if mask.any() else np.nan,
                     "bets_per_season": r["bets"] / sub["season"].nunique()})
    # by season for the 2% rule, to see whether it holds up year by year
    e = 0.02
    by_season = []
    for season, g in sub.groupby("season"):
        i = g.index.to_numpy()
        mask = np.zeros_like(O, dtype=bool)
        mask[i] = np.isfinite(ev[i]) & (ev[i] > e)
        by_season.append({"season": season, **ef.flat_return(O, Ys, mask, seed=1)})
    # where do the generous prices sit? share of qualifying bets by outcome
    mask = np.isfinite(ev) & (ev > e)
    share = dict(zip(["home", "draw", "away"], (mask.sum(0) / max(mask.sum(), 1)).round(3).tolist()))
    return {"matches": int(len(sub)), "rules": pd.DataFrame(rows), "by_season": pd.DataFrame(by_season),
            "outcome_share": share}


def by_season(m: pd.DataFrame, Y: np.ndarray) -> pd.DataFrame:
    """Calibration slope and the long-shot gap, season by season."""
    rows = []
    for season, g in m.groupby("season"):
        i = g.index.to_numpy()
        P = margin.proportional(g[cols("avg")].to_numpy())
        O = g[cols("avg")].to_numpy()
        ok = np.isfinite(P).all(1)
        sl = ef.calibration_slope(P[ok], Y[i][ok], n_boot=200, seed=1)
        fav = ef.flat_return(O, Y[i], O < 2.0)["return"]
        lng = ef.flat_return(O, Y[i], O >= 5.0)["return"]
        rows.append({"season": season, "matches": len(g), **sl, "fav_return": fav, "longshot_return": lng,
                     "longshot_gap": fav - lng, "margin": float(np.median(margin.overround(O[ok])))})
    t = pd.DataFrame(rows)
    # trend in the slope across seasons (weighted least squares, weights from the interval width)
    x = np.arange(len(t))
    w = 1 / ((t["slope_hi"] - t["slope_lo"]) / 3.92) ** 2
    X = np.column_stack([np.ones_like(x), x])
    beta = np.linalg.solve(X.T @ (X * w.to_numpy()[:, None]), X.T @ (w.to_numpy() * t["slope"].to_numpy()))
    se = np.sqrt(np.linalg.inv(X.T @ (X * w.to_numpy()[:, None]))[1, 1])
    t.attrs["trend_per_decade"] = (float(beta[1] * 10), float(se * 10))
    return t


def by_league(m: pd.DataFrame, Y: np.ndarray) -> pd.DataFrame:
    rows = []
    for lg, g in m.groupby("league"):
        i = g.index.to_numpy()
        O = g[cols("avg")].to_numpy()
        P = margin.proportional(O)
        ok = np.isfinite(P).all(1)
        sl = ef.calibration_slope(P[ok], Y[i][ok], n_boot=300, seed=2)
        rows.append({"league": lg, "matches": len(g), **sl,
                     "margin": float(np.median(margin.overround(O[ok]))),
                     "bet_everything": ef.flat_return(O, Y[i])["return"],
                     "longshot_return": ef.flat_return(O, Y[i], O >= 5.0)["return"],
                     "fav_return": ef.flat_return(O, Y[i], O < 2.0)["return"]})
    return pd.DataFrame(rows)
