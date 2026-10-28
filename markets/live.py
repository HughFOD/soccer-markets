"""What happens after half-time: a test of a simple in-play pricing model.

In-play (live) odds are not in the data, but half-time scores are. A simple
way to price a match at half-time is:

1. Turn the pre-match odds into each team's expected goals (the Poisson
   rates that reproduce the market's home-win and away-win probabilities).
2. Assume the second half is the rest of the same match: each team scores at
   its pre-match rate, times the share of goals that fall after half-time.
3. Add the half-time score and read off home win / draw / away win.

If teams played the second half the same way whatever the score, this would
be right. The test is where it goes wrong.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import poisson

from . import efficiency as ef, margin

G = np.arange(0, 13)


def _grid():
    lam = np.arange(0.15, 4.5, 0.01)
    lh, la = np.meshgrid(lam, lam, indexing="ij")
    lh, la = lh.ravel(), la.ravel()
    ph = poisson.pmf(G[None, :], lh[:, None])
    pa = poisson.pmf(G[None, :], la[:, None])
    # P(home goals > away goals) and the reverse, for each (lh, la)
    cdf_a = np.cumsum(pa, axis=1)
    cdf_h = np.cumsum(ph, axis=1)
    p_home = (ph[:, 1:] * cdf_a[:, :-1]).sum(1)
    p_away = (pa[:, 1:] * cdf_h[:, :-1]).sum(1)
    return lh, la, np.column_stack([p_home, p_away])


_LH, _LA, _PTS = _grid()
_TREE = cKDTree(_PTS)


def implied_rates(P: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Expected goals for home and away that reproduce the market's P(home win) and P(away win)."""
    _, i = _TREE.query(P[:, [0, 2]])
    return _LH[i], _LA[i]


def final_probs(ht_h, ht_a, rem_h, rem_a) -> np.ndarray:
    """Home / draw / away given the half-time score and expected second-half goals."""
    ph = poisson.pmf(G[None, :], rem_h[:, None])
    pa = poisson.pmf(G[None, :], rem_a[:, None])
    diff0 = (ht_h - ht_a).astype(int)
    out = np.zeros((len(rem_h), 3))
    grid = ph[:, :, None] * pa[:, None, :]
    d = G[:, None] - G[None, :]                       # second-half goal difference
    for k in np.unique(diff0):
        s = diff0 == k
        tot = d[None] + k
        out[s, 0] = (grid[s] * (tot > 0)).sum((1, 2))
        out[s, 1] = (grid[s] * (tot == 0)).sum((1, 2))
        out[s, 2] = (grid[s] * (tot < 0)).sum((1, 2))
    return out / out.sum(1, keepdims=True)


def prepare(m: pd.DataFrame) -> pd.DataFrame:
    d = m.dropna(subset=["ht_hg", "ht_ag"]).copy()
    P = margin.power(d[["avg_h", "avg_d", "avg_a"]].to_numpy())
    ok = np.isfinite(P).all(1)
    d, P = d[ok].copy(), P[ok]
    d["pre_h"], d["pre_d"], d["pre_a"] = P.T
    d["lam_h"], d["lam_a"] = implied_rates(P)
    total = (d["hg"] + d["ag"]).sum()
    share2 = 1 - (d["ht_hg"] + d["ht_ag"]).sum() / total
    # scale the rates so expected full-time goals match the data overall (the market's draw price is ignored by the fit)
    scale = total / (d["lam_h"] + d["lam_a"]).sum()
    d["lam_h"] *= scale
    d["lam_a"] *= scale
    d["rem_h"], d["rem_a"] = d["lam_h"] * share2, d["lam_a"] * share2
    d["sh_h"], d["sh_a"] = d["hg"] - d["ht_hg"], d["ag"] - d["ht_ag"]
    d.attrs.update(share_second_half=float(share2), rate_scale=float(scale))
    return d.reset_index(drop=True)


def score_effects(d: pd.DataFrame) -> pd.DataFrame:
    """Second-half goals, actual ÷ expected, by the team's half-time situation."""
    # stack home and away into one row per team-match
    team = pd.DataFrame({
        "margin": np.concatenate([d["ht_hg"] - d["ht_ag"], d["ht_ag"] - d["ht_hg"]]),
        "scored": np.concatenate([d["sh_h"], d["sh_a"]]),
        "expected": np.concatenate([d["rem_h"], d["rem_a"]]),
        "match": np.concatenate([np.arange(len(d))] * 2),
    })
    team["margin"] = team["margin"].clip(-2, 2)
    rows = []
    for k, g in team.groupby("margin"):
        r, lo, hi = ef.ratio_ci(g["scored"].to_numpy(), g["expected"].to_numpy(), n_boot=1000, seed=int(k) + 5)
        rows.append({"margin": int(k), "teams": len(g), "scored_per_team": g["scored"].mean(),
                     "expected_per_team": g["expected"].mean(), "ratio": r, "lo": lo, "hi": hi})
    return pd.DataFrame(rows)


def by_state(d: pd.DataFrame, P_live: np.ndarray) -> pd.DataFrame:
    """Actual vs model at half-time for the pre-match favourite, by half-time situation."""
    Y = np.column_stack([(d["result"] == o).to_numpy() for o in "HDA"]).astype(float)
    fav_home = (d["pre_h"] >= d["pre_a"]).to_numpy()
    fav_pre = np.where(fav_home, d["pre_h"], d["pre_a"])
    fav_margin = np.where(fav_home, d["ht_hg"] - d["ht_ag"], d["ht_ag"] - d["ht_hg"])
    fav_win = np.where(fav_home, Y[:, 0], Y[:, 2])
    fav_win_model = np.where(fav_home, P_live[:, 0], P_live[:, 2])
    draw, draw_model = Y[:, 1], P_live[:, 1]
    strength = np.where(fav_pre >= 0.6, "strong favourite (60%+)", "narrow favourite")
    rows = []
    for st in ("strong favourite (60%+)", "narrow favourite"):
        for k, label in ((-1, "trailing by 1"), (0, "level"), (1, "leading by 1"), (2, "leading by 2+")):
            s = (strength == st) & ((fav_margin == k) if k < 2 else (fav_margin >= 2))
            if s.sum() < 50:
                continue
            diff = ef.mean_ci(fav_win[s] - fav_win_model[s], n_boot=1000, seed=k + 10)
            ddraw = ef.mean_ci(draw[s] - draw_model[s], n_boot=1000, seed=k + 20)
            rows.append({"favourite": st, "half_time": label, "matches": int(s.sum()),
                         "pre_match_win": float(fav_pre[s].mean()),
                         "model_win": float(fav_win_model[s].mean()), "actual_win": float(fav_win[s].mean()),
                         "win_gap": diff[0], "win_lo": diff[1], "win_hi": diff[2],
                         "model_draw": float(draw_model[s].mean()), "actual_draw": float(draw[s].mean()),
                         "draw_gap": ddraw[0], "draw_lo": ddraw[1], "draw_hi": ddraw[2]})
    return pd.DataFrame(rows)


def adjusted_model(d: pd.DataFrame, effects: pd.DataFrame, train: np.ndarray) -> np.ndarray:
    """Same model, but each team's second-half rate is multiplied by the score-effect ratio
    for its half-time situation, estimated on `train` matches only."""
    tr = d[train]
    team = pd.DataFrame({
        "margin": np.concatenate([tr["ht_hg"] - tr["ht_ag"], tr["ht_ag"] - tr["ht_hg"]]).clip(-2, 2),
        "scored": np.concatenate([tr["sh_h"], tr["sh_a"]]),
        "expected": np.concatenate([tr["rem_h"], tr["rem_a"]]),
    })
    g = team.groupby("margin")[["scored", "expected"]].sum()
    mult = (g["scored"] / g["expected"]).to_dict()
    mh = (d["ht_hg"] - d["ht_ag"]).clip(-2, 2).map(mult).to_numpy()
    ma = (d["ht_ag"] - d["ht_hg"]).clip(-2, 2).map(mult).to_numpy()
    return final_probs(d["ht_hg"].to_numpy(), d["ht_ag"].to_numpy(), d["rem_h"].to_numpy() * mh, d["rem_a"].to_numpy() * ma)


def run(m: pd.DataFrame) -> dict:
    d = prepare(m)
    Y = np.column_stack([(d["result"] == o).to_numpy() for o in "HDA"]).astype(float)
    P_live = final_probs(d["ht_hg"].to_numpy(), d["ht_ag"].to_numpy(), d["rem_h"].to_numpy(), d["rem_a"].to_numpy())
    effects = score_effects(d)
    states = by_state(d, P_live)
    # does correcting for score effects help? fit on seasons before 2010, test after
    train = (d["date"] < pd.Timestamp("2010-07-01")).to_numpy()
    P_adj = adjusted_model(d, effects, train)
    te = ~train
    ll_naive, ll_adj = ef.log_loss(P_live[te], Y[te]), ef.log_loss(P_adj[te], Y[te])
    ll_pre = ef.log_loss(d.loc[te, ["pre_h", "pre_d", "pre_a"]].to_numpy(), Y[te])
    states_adj = by_state(d[te].reset_index(drop=True), P_adj[te])
    return {"matches": len(d), "share_second_half": d.attrs["share_second_half"],
            "score_effects": effects, "by_state": states, "by_state_adjusted_test": states_adj,
            "test_matches": int(te.sum()),
            "log_loss": {"pre_match": float(ll_pre.mean()), "half_time_naive": float(ll_naive.mean()),
                         "half_time_adjusted": float(ll_adj.mean())},
            "adjusted_gain": ef.mean_ci(ll_naive - ll_adj)}
