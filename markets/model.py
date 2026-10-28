"""A statistical model built only from past scores, refitted every week.

Each team gets an attack and a defence rating; home teams get a bonus.
Goals are Poisson (Maher 1982; Dixon & Coles 1997):

    home goals ~ Poisson(exp(mu + home + attack[home] - defence[away]))
    away goals ~ Poisson(exp(mu +        attack[away] - defence[home]))

Older matches count less (weights halve every `half_life` days). The model is
walk-forward: matches in week w are predicted from a fit on matches strictly
before week w, so it never sees the future. The test in tests/ checks that.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import poisson
from sklearn.linear_model import PoissonRegressor

MAX_GOALS = 10


def _design(m: pd.DataFrame, teams: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Two rows per match (home goals, away goals). Columns: attack[t], -defence[t], home."""
    idx = {t: i for i, t in enumerate(teams)}
    n, k = len(m), len(teams)
    X = np.zeros((2 * n, 2 * k + 1))
    h = m["home"].map(idx).to_numpy()
    a = m["away"].map(idx).to_numpy()
    r = np.arange(n)
    X[2 * r, h] = 1
    X[2 * r, k + a] = 1
    X[2 * r, 2 * k] = 1
    X[2 * r + 1, a] = 1
    X[2 * r + 1, k + h] = 1
    y = np.empty(2 * n)
    y[0::2], y[1::2] = m["hg"].to_numpy(), m["ag"].to_numpy()
    return X, y


def fit(past: pd.DataFrame, at: pd.Timestamp, half_life: float = 180.0, window_days: int = 3 * 365,
        alpha: float = 1e-3):
    past = past[(past["date"] < at) & (past["date"] >= at - pd.Timedelta(days=window_days))]
    teams = sorted(set(past["home"]) | set(past["away"]))
    X, y = _design(past, teams)
    age = (at - past["date"]).dt.days.to_numpy()
    w = np.repeat(0.5 ** (age / half_life), 2)
    reg = PoissonRegressor(alpha=alpha / len(y), max_iter=300).fit(X, y, sample_weight=w)
    return reg, teams


def rates(reg, teams: list[str], fixtures: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Expected goals. A team with no history gets the average of the bottom quarter
    of current teams (new teams in a league are usually promoted, so weaker)."""
    k = len(teams)
    att, dfn, home = reg.coef_[:k], reg.coef_[k:2 * k], reg.coef_[2 * k]
    lo_att, lo_dfn = np.quantile(att, 0.25), np.quantile(dfn, 0.75)  # weak = low attack, high (bad) column value
    idx = {t: i for i, t in enumerate(teams)}

    def a(t):
        return att[idx[t]] if t in idx else lo_att

    def d(t):
        return dfn[idx[t]] if t in idx else lo_dfn
    lh = np.exp(reg.intercept_ + home + np.array([a(t) for t in fixtures["home"]]) + np.array([d(t) for t in fixtures["away"]]))
    la = np.exp(reg.intercept_ + np.array([a(t) for t in fixtures["away"]]) + np.array([d(t) for t in fixtures["home"]]))
    return lh, la


def outcome_probs(lh: np.ndarray, la: np.ndarray) -> np.ndarray:
    g = np.arange(MAX_GOALS + 1)
    ph = poisson.pmf(g[None, :], lh[:, None])
    pa = poisson.pmf(g[None, :], la[:, None])
    grid = ph[:, :, None] * pa[:, None, :]             # match x home goals x away goals
    home = np.tril(np.ones((MAX_GOALS + 1,) * 2), -1)  # home goals > away goals
    P = np.column_stack([(grid * home).sum((1, 2)), np.trace(grid, axis1=1, axis2=2), (grid * home.T).sum((1, 2))])
    return P / P.sum(axis=1, keepdims=True)


def walk_forward(m: pd.DataFrame, min_history_days: int = 365, **kw) -> pd.DataFrame:
    """Predict every match from matches in the same league strictly before its week.

    Returns columns model_h, model_d, model_a, model_fit_end (the last date the
    fit could see), for matches with at least a year of history; others NaN.
    """
    out = pd.DataFrame(index=m.index, columns=["model_h", "model_d", "model_a"], dtype=float)
    out["model_fit_end"] = pd.NaT
    for lg, g in m.groupby("league"):
        start = g["date"].min() + pd.Timedelta(days=min_history_days)
        week = g["date"].dt.to_period("W-MON").dt.start_time
        for wk, fixtures in g[g["date"] >= start].groupby(week[g["date"] >= start]):
            past = g[g["date"] < wk]
            reg, teams = fit(past, wk, **kw)
            P = outcome_probs(*rates(reg, teams, fixtures))
            out.loc[fixtures.index, ["model_h", "model_d", "model_a"]] = P
            out.loc[fixtures.index, "model_fit_end"] = past["date"].max()
    return out
