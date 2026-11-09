"""Extra studies on the historical odds (football-data.co.uk, six leagues since 2000):

  draws    - are draws priced as accurately as home and away wins with the same chance?
  popular  - are the biggest, most-backed clubs worse value than other teams at the same odds?
  crowds   - what happened to home advantage when stadiums were empty (2020-21), and how fast did the odds adjust?
  early    - are the odds less accurate in the first weeks of a season, or for newly promoted teams?
  stakes   - late in the season, are teams with nothing left to play for priced too high?
  totals   - does the long-shot pattern hold for over/under 2.5 goals?

Results go to output/studies.json, which the research page reads.
Run: python -m markets.studies
"""
from __future__ import annotations

import json
import re
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


STAGES = [(1, 5, "Rounds 1–5"), (6, 10, "Rounds 6–10"), (11, 19, "Rounds 11–19"), (20, 29, "Rounds 20–29"), (30, 99, "Round 30 on")]
TOP = {"E0": 7, "SP1": 7, "I1": 7, "D1": 7, "F1": 5, "E1": 6}   # finishing places that still mean Europe or promotion
RELEGATED = 3


def _prev(season: str) -> str:
    a = int(season[:4])
    return f"{a - 1}-{a}"


def rounds(m: pd.DataFrame) -> np.ndarray:
    """Each match's round: the higher of the two teams' game numbers that season."""
    idx = np.arange(len(m))
    t = pd.concat([pd.DataFrame({"k": m["league"] + m["season"] + "|" + m["home"], "date": m["date"], "i": idx}),
                   pd.DataFrame({"k": m["league"] + m["season"] + "|" + m["away"], "date": m["date"], "i": idx})])
    t = t.sort_values(["date", "i"], kind="stable")
    t["n"] = t.groupby("k").cumcount() + 1
    return t.groupby("i")["n"].max().reindex(idx).to_numpy()


def early(m: pd.DataFrame, L: pd.DataFrame) -> dict:
    """$100 on every result by stage of the season, and newly promoted teams against the rest."""
    rnd = rounds(m)
    L = L.assign(round=rnd[L["match"].to_numpy()])
    stages = []
    for lo, hi, name in STAGES:
        x = L[L["round"].between(lo, hi)]
        stages.append({"stage": name, "ret": _ci(x["profit"]), "matches": int(x["match"].nunique())})
    teams = {k: set(g["home"]) | set(g["away"]) for k, g in m.groupby(["league", "season"])}
    known = np.array([(l, _prev(s)) in teams for l, s in zip(m["league"], m["season"])])
    new = lambda col: np.array([(l, _prev(s)) in teams and t not in teams[(l, _prev(s))]
                                for l, s, t in zip(m["league"], m["season"], m[col])])
    h_new, a_new = new("home"), new("away")
    w = L[(L["outcome"] != "draw") & known[L["match"].to_numpy()]].copy()
    i = w["match"].to_numpy()
    w["new"] = np.where(w["outcome"] == "home", h_new[i], a_new[i])
    w["first10"] = w["round"] <= 10
    out = {}
    for name, x in (("new_early", w[w["new"] & w["first10"]]), ("new_all", w[w["new"]]), ("others", w[~w["new"]])):
        out[name] = {"priced": float(x["chance"].mean()), "happened": float(x["won"].mean()),
                     "gap": _ci(x["won"] - x["chance"]), "ret": _ci(x["profit"])}
    return {"stages": stages, "promoted": out}


def standings_stakes(m: pd.DataFrame, last: int = 8) -> tuple[np.ndarray, np.ndarray]:
    """For each team in its last `last` games of a finished season: 1 if it can still finish in the places for
    Europe or promotion, or can still be relegated; 0 if it has nothing left to play for. NaN otherwise."""
    sh, sa = np.full(len(m), np.nan), np.full(len(m), np.nan)
    for (lg, _), g in m.groupby(["league", "season"]):
        teams = sorted(set(g["home"]) | set(g["away"]))
        n = len(teams)
        games = 2 * (n - 1)
        if len(g) < 0.95 * n * (n - 1) or lg not in TOP:
            continue     # the season still being played
        pts = dict.fromkeys(teams, 0)
        pl = dict.fromkeys(teams, 0)
        for _, day in g.groupby("date", sort=True):
            mx = {u: pts[u] + 3 * (games - pl[u]) for u in teams}
            for i, h, a in zip(day.index, day["home"], day["away"]):
                for t, arr in ((h, sh), (a, sa)):
                    if games - pl[t] > last:
                        continue
                    safe = sum(u != t and mx[u] >= pts[t] for u in teams) <= n - RELEGATED - 1
                    no_top = sum(u != t and pts[u] > mx[t] for u in teams) >= TOP[lg]
                    arr[i] = 0.0 if (safe and no_top) else 1.0
            for h, a, r in zip(day["home"], day["away"], day["result"]):
                pl[h] += 1
                pl[a] += 1
                pts[h] += 3 if r == "H" else 1 if r == "D" else 0
                pts[a] += 3 if r == "A" else 1 if r == "D" else 0
    return sh, sa


def stakes(m: pd.DataFrame, L: pd.DataFrame) -> dict:
    """Last eight games of the season: teams with something to play for against teams with nothing."""
    sh, sa = standings_stakes(m.reset_index(drop=True))
    i = L["match"].to_numpy()
    mine = np.where(L["outcome"] == "home", sh[i], np.where(L["outcome"] == "away", sa[i], np.nan))
    theirs = np.where(L["outcome"] == "home", sa[i], np.where(L["outcome"] == "away", sh[i], np.nan))
    w = L.assign(mine=mine, theirs=theirs).dropna(subset=["mine", "theirs"])
    out = {}
    for name, a, b in (("motivated_vs_not", 1, 0), ("not_vs_motivated", 0, 1), ("both", 1, 1), ("neither", 0, 0)):
        x = w[(w["mine"] == a) & (w["theirs"] == b)]
        out[name] = {"priced": float(x["chance"].mean()), "happened": float(x["won"].mean()),
                     "gap": _ci(x["won"] - x["chance"]), "ret": _ci(x["profit"])}
    out["matches"] = int(np.isfinite(sh).sum())
    return out


def totals(raw: Path) -> dict | None:
    """Over/under 2.5 goals at the average price across bookmakers: how often each side happened against its chance
    (cut removed), and the result of $100 on it, by how likely the odds made it."""
    rows = []
    for f in sorted(raw.glob("*.csv")):
        if not re.fullmatch(r"[A-Z0-9]+_\d{4}-\d{4}", f.stem):
            continue
        d = pd.read_csv(f, encoding="latin1", on_bad_lines="skip")
        o = next((c for c in ("Avg>2.5", "BbAv>2.5") if c in d), None)
        if not o or "FTHG" not in d:
            continue
        num = lambda c: pd.to_numeric(d[c], errors="coerce")
        rows.append(pd.DataFrame({"goals": num("FTHG") + num("FTAG"), "over": num(o), "under": num(o.replace(">", "<"))}))
    if not rows:
        return None
    t = pd.concat(rows).dropna()
    t = t[(t["over"] > 1) & (t["under"] > 1)]
    inv = 1 / t["over"] + 1 / t["under"]
    p = (1 / t["over"]) / inv
    B = pd.concat([pd.DataFrame({"side": "Over 2.5", "chance": p, "won": t["goals"] >= 3, "odds": t["over"]}),
                   pd.DataFrame({"side": "Under 2.5", "chance": 1 - p, "won": t["goals"] < 3, "odds": t["under"]})])
    B["profit"] = B["won"] * B["odds"] - 1
    bands = []
    for lo, hi, name in ((0, .35, "Under 35%"), (.35, .45, "35–45%"), (.45, .55, "45–55%"), (.55, .65, "55–65%"), (.65, 1.01, "65% or more")):
        x = B[(B["chance"] >= lo) & (B["chance"] < hi)]
        bands.append({"band": name, "priced": float(x["chance"].mean()), "happened": float(x["won"].mean()), "ret": _ci(x["profit"])})
    sides = {s: {"priced": float(x["chance"].mean()), "happened": float(x["won"].mean()), "ret": _ci(x["profit"])}
             for s, x in B.groupby("side")}
    return {"matches": int(len(t)), "margin": float((inv - 1).mean()), "bands": bands, "sides": sides}


def main(raw: Path = ROOT / "data" / "raw", out: Path = ROOT / "output" / "studies.json"):
    m = data.load(raw)
    L = _long(m)
    R = {"matches": int(len(m)), "draws": draws(L), "popular": popular(L), "crowds": crowds(m, L),
         "early": early(m, L), "stakes": stakes(m, L), "totals": totals(raw)}
    out.write_text(json.dumps(R, indent=1))
    print(f"wrote {out}")
    return R


if __name__ == "__main__":
    main()
