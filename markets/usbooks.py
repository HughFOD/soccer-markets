"""This week's soccer odds at American sportsbooks and prediction markets, from The Odds API.

Needs an API key saved in odds_api_key.txt in the project folder (or the
ODDS_API_KEY environment variable). One refresh of six leagues uses 12 credits
for match results and 12 for goals over/under (two regions per league): about
720 a month of the 20K plan's 20,000.

- Sites: FanDuel, DraftKings, Fanatics, BetMGM and Caesars, plus the prediction
  markets Kalshi and Polymarket (largest first). Every other site is ignored.
- Consensus: every site's odds turned into chances with its margin removed,
  then averaged with equal weight. No site counts more than another.
- Flags: a site whose odds are more than 2% better than the consensus
  (and no more than 25%, which is almost always a stale or mistyped price).
"""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .consensus import _probs
from .fairprice import MAX_EDGE, pool

ROOT = Path(__file__).resolve().parent.parent
SPORTS = {"soccer_epl": "Premier League", "soccer_efl_champ": "Championship", "soccer_spain_la_liga": "La Liga",
          "soccer_germany_bundesliga": "Bundesliga", "soccer_italy_serie_a": "Serie A",
          "soccer_france_ligue_one": "Ligue 1"}
REGIONS = ("us", "us_ex")
SITES = {  # key -> (display name, kind). Only these sites are used, listed by US market share
    # (sportsbooks: Q3 2026 revenue share; prediction markets: trading volume).
    "fanduel": ("FanDuel", "Sportsbook"), "draftkings": ("DraftKings", "Sportsbook"),
    "fanatics": ("Fanatics", "Sportsbook"), "betmgm": ("BetMGM", "Sportsbook"),
    "williamhill_us": ("Caesars", "Sportsbook"),
    "kalshi": ("Kalshi", "Prediction market"), "polymarket": ("Polymarket", "Prediction market"),
}
THRESHOLD = 0.02

# Prediction markets quote prices before their trading fee; sportsbooks build their cut into the odds.
# To compare like with like, Kalshi and Polymarket odds are converted to what a bettor actually gets
# after the fee for buying at the listed price (a "taker" trade). Both charge
#   fee per contract = rate x price x (1 - price)      (price in dollars, contract pays $1)
# Kalshi: rate 0.07 (its general fee schedule). Polymarket US: rate 0.05 for sports (from July 2026).
# Both round the fee up to the next cent per order, which is ignored here (it matters only for tiny orders).
FEE_RATES = {"kalshi": 0.07, "polymarket": 0.05}


def after_fees(site: str, odds: float) -> float:
    """Decimal odds a bettor really gets at `site` once its trading fee is paid."""
    rate = FEE_RATES.get(site)
    if not rate or odds is None or not np.isfinite(odds) or odds <= 1:
        return odds
    p = 1 / odds
    return 1 / (p + rate * p * (1 - p))


TOTALS_REGION = "us,us_ex"   # goals over/under: sportsbooks and prediction markets
TOTALS_MAX_LEAGUES = 2  # used only when limiting goals odds to the busiest leagues
TOTALS_ALL_ABOVE = 2000  # with more credits than this left (a paid plan), fetch goals odds for every league
TOTALS_DAYS = 1        # fetch goals over/under for leagues with a match today (New York time); keeps the free plan under 500 a month
ET = "America/New_York"


def api_key() -> str | None:
    if os.environ.get("ODDS_API_KEY"):
        return os.environ["ODDS_API_KEY"].strip()
    f = ROOT / "odds_api_key.txt"
    return f.read_text().strip() if f.exists() else None


def fetch(key: str, sport: str, region: str, markets: str = "h2h") -> tuple[list, str | None]:
    url = (f"https://api.the-odds-api.com/v4/sports/{sport}/odds?regions={region}&markets={markets}"
           f"&oddsFormat=decimal&apiKey={key}")
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read()), r.headers.get("x-requests-remaining")


def download(key: str, dest: Path) -> dict:
    """Save the raw responses (so pages can be rebuilt without spending credits)."""
    out, remaining = {}, None
    for sport in SPORTS:
        for region in REGIONS:
            try:
                out[f"{sport}|{region}"], remaining = fetch(key, sport, region)
            except Exception as e:  # league out of season, or a temporary error
                print(f"  skipped {sport} {region}: {e}")
                out[f"{sport}|{region}"] = []
    try:
        paid = float(remaining) > TOTALS_ALL_ABOVE
    except (TypeError, ValueError):
        paid = False
    for sport in (SPORTS if paid else soon_sports(out)):
        try:
            out[f"{sport}|{TOTALS_REGION}|totals"], remaining = fetch(key, sport, TOTALS_REGION, "totals")
        except Exception as e:
            print(f"  skipped {sport} totals: {e}")
    from . import extras
    before = remaining
    ext, remaining = extras.download(key, out, remaining)
    if ext:
        try:
            used = float(before) - float(remaining)
        except (TypeError, ValueError):
            used = float("nan")
        print(f"  extra markets for {len(ext)} matches ({used:.0f} credits)")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"fetched": datetime.now(timezone.utc).isoformat(), "remaining": remaining,
                                "data": out, "extras": ext}))
    print(f"  saved {dest.name}; API credits left this month: {remaining}")
    return out


def soon_sports(raw: dict, now: pd.Timestamp | None = None, days: int = TOTALS_DAYS,
                limit: int = TOTALS_MAX_LEAGUES) -> list[str]:
    """Leagues with a match kicking off between now and the end of the last of `days` days:
    the `limit` leagues with the most such matches."""
    now = now or pd.Timestamp.now(tz=ET)
    end = (now.tz_convert(ET).normalize() + pd.Timedelta(days=days))
    count: dict[str, set] = {}
    for k, events in raw.items():
        if k.endswith("|totals"):
            continue
        sport = k.split("|")[0]
        for ev in events:
            ko = pd.Timestamp(ev["commence_time"]).tz_convert(ET)
            if now < ko < end:
                count.setdefault(sport, set()).add(ev["id"])
    return sorted(count, key=lambda s: -len(count[s]))[:limit]


def totals_table(raw: dict) -> pd.DataFrame:
    """One row per match, site and goals line: decimal odds for over and under."""
    rows = []
    for k, events in raw.items():
        if not k.endswith("|totals"):
            continue
        sport = k.split("|")[0]
        for ev in events:
            for bk in ev.get("bookmakers", []):
                if bk["key"] not in SITES:
                    continue
                mk = next((m for m in bk.get("markets", []) if m.get("key") == "totals"), None)
                if not mk:
                    continue
                by_point = {}
                for o in mk.get("outcomes", []):
                    if o.get("point") is not None and o.get("name") in ("Over", "Under"):
                        by_point.setdefault(float(o["point"]), {})[o["name"]] = after_fees(bk["key"], o["price"])
                for point, pr in by_point.items():
                    if "Over" in pr and "Under" in pr:
                        rows.append({"id": ev["id"], "league": SPORTS.get(sport, sport), "kickoff": ev["commence_time"],
                                     "home": ev["home_team"], "away": ev["away_team"], "site": bk["key"],
                                     "point": point, "over": pr["Over"], "under": pr["Under"]})
    t = pd.DataFrame(rows)
    return t.drop_duplicates(["id", "site", "point"]).reset_index(drop=True) if len(t) else t


def price_totals(t: pd.DataFrame, min_sites: int = 3) -> pd.DataFrame:
    """Goals over/under, priced the same way as match results.

    For each match and goals line quoted by at least `min_sites` sites: every site's over/under odds
    become chances with its cut removed, the chances are pooled with equal weight into the expected
    chance, and each site's expected return is expected chance x decimal odds - 1.
    One row per match, line, side and site.
    """
    out = []
    if t is None or not len(t):
        return pd.DataFrame(out)
    for (mid, point), g in t.groupby(["id", "point"], sort=False):
        O = g[["over", "under"]].to_numpy(float)
        P = _probs(O)
        ok = np.isfinite(P).all(1)
        g, O, P = g[ok], O[ok], P[ok]
        if len(g) < min_sites:
            continue
        C = pool(np.log(P)[:, None, :], np.ones(len(g)) / len(g), 1.0)[0]
        r0 = g.iloc[0]
        for k, side in enumerate(("Over", "Under")):
            E = C[k] * O[:, k] - 1
            best = O[:, k].max()
            for i in range(len(g)):
                out.append({"id": mid, "league": r0["league"], "kickoff": r0["kickoff"], "home": r0["home"],
                            "away": r0["away"], "point": point, "side": side, "site": g["site"].iloc[i],
                            "odds": O[i, k], "chance": C[k], "edge": E[i], "best": bool(np.isclose(O[i, k], best))})
    return pd.DataFrame(out)


def to_table(raw: dict) -> pd.DataFrame:
    """One row per match and site: decimal odds for home, draw and away. Only the sites in SITES."""
    rows = []
    for k, events in raw.items():
        sport = k.split("|")[0]
        for ev in events:
            for bk in ev.get("bookmakers", []):
                if bk["key"] not in SITES:
                    continue
                h2h = next((mk for mk in bk.get("markets", []) if mk.get("key") == "h2h"), None)
                if not h2h:
                    continue
                price = {o["name"]: after_fees(bk["key"], o["price"]) for o in h2h.get("outcomes", [])}
                oh, od, oa = price.get(ev["home_team"]), price.get("Draw"), price.get(ev["away_team"])
                if None in (oh, od, oa):
                    continue
                rows.append({"id": ev["id"], "league": SPORTS.get(sport, sport), "kickoff": ev["commence_time"],
                             "home": ev["home_team"], "away": ev["away_team"], "site": bk["key"], "h": oh, "d": od, "a": oa})
    t = pd.DataFrame(rows)
    return t.drop_duplicates(["id", "site"]).reset_index(drop=True) if len(t) else t


def american(dec: float) -> str:
    if dec is None or not np.isfinite(dec) or dec <= 1:
        return ""
    return f"+{100 * (dec - 1):.0f}" if dec >= 2 else f"{-100 / (dec - 1):.0f}"


def price(t: pd.DataFrame, threshold: float = THRESHOLD, min_sites: int = 3) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (matches, quotes).

    matches: one row per match with the consensus chance and odds for each result,
      the best price and site, and any flags.
    quotes: one row per match, site and result, with the site's odds and its edge
      over the consensus (positive = better than the consensus).
    """
    matches, quotes = [], []
    for mid, g in t.groupby("id", sort=False):
        O = g[["h", "d", "a"]].to_numpy(float)
        P = _probs(O)
        ok = np.isfinite(P).all(1)
        g, O, P = g[ok], O[ok], P[ok]
        if len(g) < min_sites:
            continue
        C = pool(np.log(P)[:, None, :], np.ones(len(g)) / len(g), 1.0)[0]
        r0 = g.iloc[0]
        row = {"id": mid, "league": r0["league"], "kickoff": r0["kickoff"], "home": r0["home"], "away": r0["away"],
               "n_sites": len(g), "sites": ",".join(g["site"])}
        flags = []
        for k, (o, lab) in enumerate(zip("hda", ("Home", "Draw", "Away"))):
            E = C[k] * O[:, k] - 1
            j = int(np.argmax(O[:, k]))
            row.update({f"cons_{o}": C[k], f"cons_us_{o}": american(1 / C[k]), f"best_{o}": O[j, k],
                        f"best_us_{o}": american(O[j, k]), f"best_site_{o}": SITES[g["site"].iloc[j]][0], f"edge_{o}": E[j]})
            if threshold < E[j] <= MAX_EDGE:
                flags.append(f"{lab} {american(O[j, k])} at {SITES[g['site'].iloc[j]][0]} ({E[j]:+.1%} vs consensus)")
            for i in range(len(g)):
                quotes.append({"id": mid, "site": g["site"].iloc[i], "result": o, "odds": O[i, k], "edge": E[i],
                               "best": i == j or O[i, k] == O[j, k]})
        row["flag"] = "; ".join(flags)
        matches.append(row)
    M = pd.DataFrame(matches)
    if len(M):
        M = M.sort_values("kickoff").reset_index(drop=True)
    return M, pd.DataFrame(quotes)


def scoreboard(quotes: pd.DataFrame, t: pd.DataFrame) -> pd.DataFrame:
    """Which site has the best prices this week."""
    if quotes.empty:
        return pd.DataFrame()
    with np.errstate(divide="ignore"):
        margins = t.assign(margin=(1 / t[["h", "d", "a"]]).sum(1) - 1).groupby("site")["margin"].median()
    q = quotes.groupby("site").agg(matches=("id", "nunique"), avg_edge=("edge", "mean"), best_share=("best", "mean"),
                                   flagged=("edge", lambda e: int(((e > THRESHOLD) & (e <= MAX_EDGE)).sum())))
    q["margin"] = margins.reindex(q.index)
    q["name"] = [SITES[s][0] for s in q.index]
    q["kind"] = [SITES[s][1] for s in q.index]
    order = {k: i for i, k in enumerate(SITES)}  # market-share order
    return q.sort_index(key=lambda ix: ix.map(order)).reset_index()
