"""This week's prices at American sportsbooks, from The Odds API (the-odds-api.com).

Needs a free API key saved in odds_api_key.txt in the project folder (or the
ODDS_API_KEY environment variable). One refresh of six leagues uses 12 of the
free plan's 500 monthly credits.

How a match is priced
---------------------
- Fair price: a blend that mirrors the backtested engine, which gives
  Pinnacle about 70% of the weight and spreads the rest over the other
  bookmakers. Pinnacle and the European bookmakers come from the Odds API's
  "eu" region. Betting exchanges (Betfair, Matchbook, Smarkets) are left out.
- Flags: an American sportsbook whose odds are more than 2% better than fair
  (and no more than 25%, which is almost always a stale or mistyped price).
- Odds are shown in American format (+150 / -200) as well as the chance.

The backtest behind the engine uses European bookmakers (2013 to 2026),
because free historical odds from American sportsbooks do not exist. The
weekly page says so.
"""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import margin
from .fairprice import MAX_EDGE, pool

ROOT = Path(__file__).resolve().parent.parent
SPORTS = {"soccer_epl": "Premier League", "soccer_efl_champ": "Championship", "soccer_spain_la_liga": "La Liga",
          "soccer_germany_bundesliga": "Bundesliga", "soccer_italy_serie_a": "Serie A",
          "soccer_france_ligue_one": "Ligue 1"}
EXCHANGES = {"betfair_ex_eu", "betfair_ex_uk", "betfair_ex_au", "matchbook", "smarkets", "betfair"}
PINNACLE_SHARE = 0.7
# American companies licensed in US states. Other bookmakers the Odds API lists in its "us" region
# (Bovada, BetOnline, BetUS, MyBookie, LowVig) are offshore sites: they count toward the fair price
# but are not flagged.
US_LICENSED = {"draftkings", "fanduel", "betmgm", "betrivers", "williamhill_us", "espnbet", "fanatics", "hardrockbet",
               "ballybet", "betparx", "fliff", "windcreek", "superbook", "unibet_us", "pointsbetus", "wynnbet",
               "twinspires", "betfred_us", "circasports"}


def api_key() -> str | None:
    if os.environ.get("ODDS_API_KEY"):
        return os.environ["ODDS_API_KEY"].strip()
    f = ROOT / "odds_api_key.txt"
    return f.read_text().strip() if f.exists() else None


def fetch(key: str, sport: str, region: str) -> tuple[list, str | None]:
    url = (f"https://api.the-odds-api.com/v4/sports/{sport}/odds?regions={region}&markets=h2h"
           f"&oddsFormat=decimal&apiKey={key}")
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read()), r.headers.get("x-requests-remaining")


def download(key: str, dest: Path) -> dict:
    """Save the raw responses (so a run can be repeated without spending credits)."""
    out, remaining = {}, None
    for sport in SPORTS:
        for region in ("us", "eu"):
            try:
                out[f"{sport}|{region}"], remaining = fetch(key, sport, region)
            except Exception as e:  # league out of season, or a temporary error
                print(f"  skipped {sport} {region}: {e}")
                out[f"{sport}|{region}"] = []
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"fetched": datetime.now(timezone.utc).isoformat(), "remaining": remaining, "data": out}))
    print(f"  saved {dest.name}; API credits left this month: {remaining}")
    return out


def to_table(raw: dict) -> pd.DataFrame:
    """One row per match and bookmaker: decimal odds for home, draw and away, and the bookmaker's region."""
    rows = []
    for k, events in raw.items():
        sport, region = k.split("|")
        for ev in events:
            for bk in ev.get("bookmakers", []):
                h2h = next((mk for mk in bk.get("markets", []) if mk.get("key") == "h2h"), None)
                if not h2h:
                    continue
                price = {o["name"]: o["price"] for o in h2h.get("outcomes", [])}
                oh, od, oa = price.get(ev["home_team"]), price.get("Draw"), price.get(ev["away_team"])
                if None in (oh, od, oa):
                    continue
                rows.append({"id": ev["id"], "league": SPORTS.get(sport, sport), "kickoff": ev["commence_time"],
                             "home": ev["home_team"], "away": ev["away_team"], "book": bk["key"], "book_name": bk["title"],
                             "region": region, "h": oh, "d": od, "a": oa})
    t = pd.DataFrame(rows)
    if t.empty:
        return t
    # a bookmaker listed in both regions counts once, as American if it appears in the US region
    t = t.sort_values("region", key=lambda s: s.map({"us": 0, "eu": 1})).drop_duplicates(["id", "book"])
    t.loc[(t["region"] == "us") & ~t["book"].isin(US_LICENSED), "region"] = "offshore"
    return t[~t["book"].isin(EXCHANGES)].reset_index(drop=True)


def american(dec: float) -> str:
    if not np.isfinite(dec) or dec <= 1:
        return ""
    return f"+{100 * (dec - 1):.0f}" if dec >= 2 else f"{-100 / (dec - 1):.0f}"


def price(t: pd.DataFrame, threshold: float = 0.02) -> pd.DataFrame:
    """Fair price per match and the best American sportsbook price for each result."""
    out = []
    for mid, g in t.groupby("id", sort=False):
        O = g[["h", "d", "a"]].to_numpy(float)
        with np.errstate(divide="ignore", invalid="ignore"):
            over = (1 / O).sum(1) - 1
        ok = np.isfinite(O).all(1) & (over > -0.01) & (over < 0.20)
        g, O = g[ok], O[ok]
        if len(g) < 2:
            continue
        Pb = margin.power(O)
        is_pin = (g["book"] == "pinnacle").to_numpy()
        if is_pin.any() and len(g) > 1:
            w = np.where(is_pin, PINNACLE_SHARE, (1 - PINNACLE_SHARE) / max((~is_pin).sum(), 1))
        else:
            w = np.full(len(g), 1 / len(g))
        P = pool(np.log(Pb)[:, None, :], w, 1.0)[0]
        us = (g["region"] == "us").to_numpy()
        r0 = g.iloc[0]
        row = {"league": r0["league"], "kickoff": r0["kickoff"], "home": r0["home"], "away": r0["away"],
               "n_books": len(g), "n_us": int(us.sum()), "has_pinnacle": bool(is_pin.any())}
        flags = []
        for k, (o, lab) in enumerate(zip("hda", ("Home", "Draw", "Away"))):
            row[f"fair_{o}"] = P[k]
            row[f"fair_us_{o}"] = american(1 / P[k])
            if us.any():
                j = int(np.argmax(np.where(us, O[:, k], -np.inf)))
                best = O[j, k]
                edge = P[k] * best - 1
                row.update({f"best_{o}": best, f"best_us_{o}": american(best), f"best_book_{o}": g["book_name"].iloc[j],
                            f"edge_{o}": edge})
                if threshold < edge <= MAX_EDGE:
                    flags.append(f"{lab} {american(best)} at {g['book_name'].iloc[j]} ({edge:+.1%})")
            else:
                row.update({f"best_{o}": np.nan, f"best_us_{o}": "", f"best_book_{o}": "", f"edge_{o}": np.nan})
        row["flag"] = "; ".join(flags)
        out.append(row)
    return pd.DataFrame(out).sort_values("kickoff").reset_index(drop=True) if out else pd.DataFrame()
