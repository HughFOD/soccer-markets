"""Three extra studies on the historical odds (football-data.co.uk, six leagues since 2000):

  draws    - are draws priced as accurately as home and away wins with the same chance?
  popular  - are the biggest, most-backed clubs worse value than other teams at the same odds?
  crowds   - what happened to home advantage when stadiums were empty (2020-21), and how fast did the odds adjust?

Results go to output/studies.json, which the research page reads.
Run: python -m markets.studies
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import data
from .efficiency import mean_ci

ROOT = Path(__file__).resolve().parent.parent

# the clubs with the biggest worldwide followings in the six leagues (football-data.co.uk spellings)
POPULAR = ("Man United", "Liverpool", "Arsenal", "Chelsea", "Man City", "Tottenham", "Real Madrid", "Barcelona",
           "Bayern Munich", "Dortmund", "Juventus", "Milan", "Inter", "Paris SG")
EMPTY = (pd.Timestamp("2020-06-01"), pd.Timestamp("2021-05-31"))   # matches played behind closed doors
BANDS = [0.0, 0.2, 0.25, 0.3, 0.35, 1.0]


def _long(m: pd.DataFrame) -> pd.DataFrame:
    """One row per match and result: the fair chance (bookmakers' average, cut removed), the average odds
    and whether it happened."""
    Y = data.outcome_matrix(m)
    rows = []
    for i, (o, side) in enumerate((("h", "home"), ("d", "draw"), ("a", "away"))):
        rows.append(pd.DataFrame({"match": np.arange(len(m)), "date": m["date"].to_numpy(), "outcome": side,
                                  "chance": m[f"cons_{o}"].to_numpy(), "odds": m[f"avg_{o}"].to_numpy(),
                                  "won": Y[:, i], "home": m["home"].to_numpy(), "away": m["away"].to_numpy()}))
    L = pd.concat(rows, ignore_index=True)
    L = L[np.isfinite(L["odds"]) & np.isfinite(L["chance"]) & (L["odds"] > 1)]
    L["profit"] = L["won"] * L["odds"] - 1
    return L


def _ci(x) -> dict:
    est, lo, hi = mean_ci(np.asarray(x, float))
    return {"est": float(est), "lo": float(lo), "hi": float(hi), "n": int(len(x))}


def draws(L: pd.DataFrame) -> dict:
    """Draws against home or away wins given the same chance (most draws are priced 20-35%)."""
    rows = []
    for lo, hi in zip(BANDS[1:-2], BANDS[2:-1]):
        s = L[(L["chance"] >= lo) & (L["chance"] < hi)]
        for kind, g in (("draw", s[s["outcome"] == "draw"]), ("win", s[s["outcome"] != "draw"])):
            rows.append({"band": f"{100 * lo:.0f}–{100 * hi:.0f}%", "kind": kind, "priced": float(g["chance"].mean()),
                         "happened": float(g["won"].mean()), "ret": _ci(g["profit"])})
    d = L[L["outcome"] == "draw"]
    w = L[(L["outcome"] != "draw") & L["chance"].between(0.2, 0.35)]
    ds = d[d["chance"].between(0.2, 0.35)]
    return {"draw_same": {"priced": float(ds["chance"].mean()), "happened": float(ds["won"].mean()), "ret": _ci(ds["profit"])},
            "bands": rows, "draw_all": {"priced": float(d["chance"].mean()), "happened": float(d["won"].mean()),
                                        "ret": _ci(d["profit"])},
            "win_same": {"priced": float(w["chance"].mean()), "happened": float(w["won"].mean()), "ret": _ci(w["profit"])}}


def popular(L: pd.DataFrame) -> dict:
    """Backing a popular club to win, against backing any other team given the same chance."""
    wins = L[L["outcome"] != "draw"].copy()
    wins["team"] = np.where(wins["outcome"] == "home", wins["home"], wins["away"])
    wins["opp"] = np.where(wins["outcome"] == "home", wins["away"], wins["home"])
    wins["pop"] = wins["team"].isin(POPULAR)
    wins["vs_pop"] = wins["opp"].isin(POPULAR) & ~wins["pop"]
    wins["band"] = pd.cut(wins["chance"], [0, 0.35, 0.5, 0.65, 0.8, 1], labels=["<35%", "35–50%", "50–65%", "65–80%", "80%+"])
    rows = []
    for b, g in wins.groupby("band", observed=True):
        rows.append({"band": str(b), "popular": _ci(g.loc[g["pop"], "profit"]) if g["pop"].sum() > 30 else None,
                     "others": _ci(g.loc[~g["pop"] & ~g["vs_pop"], "profit"])})
    # other teams at the same odds: their result in each chance band, weighted like the big clubs' bets
    pb = [(r["popular"]["n"], r["others"]["est"]) for r in rows if r["popular"]]
    matched = sum(n * x for n, x in pb) / sum(n for n, _ in pb)
    return {"others_matched": float(matched), "bands": rows, "popular": _ci(wins.loc[wins["pop"], "profit"]),
            "others": _ci(wins.loc[~wins["pop"] & ~wins["vs_pop"], "profit"]),
            "against": _ci(wins.loc[wins["vs_pop"], "profit"]),
            "pop_chance": float(wins.loc[wins["pop"], "chance"].mean()), "teams": list(POPULAR)}


def crowds(m: pd.DataFrame, L: pd.DataFrame) -> dict:
    """Home wins: how often they happened against how often the odds expected, before, during and after empty
    stadiums, plus month by month during the empty period."""
    h = L[L["outcome"] == "home"].copy()
    h["date"] = pd.to_datetime(h["date"])
    periods = {"before": (EMPTY[0] - pd.DateOffset(years=5), EMPTY[0]), "empty": EMPTY,
               "after": (EMPTY[1] + pd.Timedelta(days=1), h["date"].max() + pd.Timedelta(days=1))}
    out = {}
    for name, (a, b) in periods.items():
        g = h[(h["date"] >= a) & (h["date"] < b)]
        idx = g["match"].to_numpy()
        gd = (m["hg"].to_numpy()[idx] - m["ag"].to_numpy()[idx])
        out[name] = {"matches": int(len(g)), "happened": float(g["won"].mean()), "priced": float(g["chance"].mean()),
                     "gap": _ci(g["won"] - g["chance"]), "goal_diff": float(gd.mean()), "home_bet": _ci(g["profit"])}
    e = h[(h["date"] >= EMPTY[0]) & (h["date"] <= EMPTY[1])].copy()
    e["month"] = e["date"].dt.to_period("M").astype(str)
    monthly = (e.groupby("month").agg(happened=("won", "mean"), priced=("chance", "mean"), matches=("won", "size"))
               .reset_index())
    monthly = monthly[monthly["matches"] >= 40]
    out["monthly"] = monthly.round(4).to_dict("records")
    return out


def main(raw: Path = ROOT / "data" / "raw", out: Path = ROOT / "output" / "studies.json"):
    m = data.load(raw)
    L = _long(m)
    R = {"matches": int(len(m)), "draws": draws(L), "popular": popular(L), "crowds": crowds(m, L)}
    out.write_text(json.dumps(R, indent=1))
    print(f"wrote {out}")
    return R


if __name__ == "__main__":
    main()
