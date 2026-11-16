"""More bets per match: corners, cards, player bets and other markets from The Odds API.

These markets are only available one match at a time (the event odds endpoint), so each match is
fetched once, on the morning of game day: matches kicking off in the next 24 hours. A match costs one
credit per market returned per region, roughly 15 to 40 credits. Only the scheduled morning run fetches
them: a run started by hand skips them, so rebuilding the site never pays for the same matches twice.

Spending cap: each morning they may use an even share of the credits left before the plan renews, after keeping
back a reserve and the cost of the daily odds for every remaining day. Biggest competitions go first.

Pricing works like match results wherever a site quotes every outcome of a bet (over and under, yes and
no, all three results): that site's odds become chances with its cut removed, the chances of every site
are pooled with equal weight into the expected chance, and each site's expected return is expected
chance x decimal odds - 1. Bets where sites quote only one side (anytime goalscorer, correct score) have
no expected chance; for those the page shows the best odds and every site's price.
"""
from __future__ import annotations

import json
import os
import urllib.request

import numpy as np
import pandas as pd

from .consensus import _probs
from .fairprice import pool
from .usbooks import after_fees, same_site

REGIONS = "us,us_ex"
WINDOW_HOURS = 24        # fetch matches kicking off within this many hours of the run
MAX_EVENTS = 60          # at most this many matches per run
RENEWS_ON = 30           # the API plan renews on this day of each month (the last day in shorter months)
RESERVE = 300            # credits always kept back for emergencies and hand-started runs
FIRST_GUESS = 30         # credits one match is assumed to cost until the run has measured it
# extra markets for the biggest competitions first, when the budget doesn't cover every match
PRIORITY = ["soccer_uefa_champs_league", "soccer_epl", "soccer_spain_la_liga", "soccer_france_ligue_one",
            "soccer_germany_bundesliga", "soccer_italy_serie_a", "soccer_uefa_europa_league"]


def days_to_renewal(today) -> int:
    """Days from today up to and including the day before the plan renews (at least 1)."""
    today = pd.Timestamp(today).normalize()
    def renewal(y, m):
        last = (pd.Timestamp(year=y, month=m, day=1) + pd.offsets.MonthEnd(0)).day
        return pd.Timestamp(year=y, month=m, day=min(RENEWS_ON, last))
    r = renewal(today.year, today.month)
    if r <= today:
        nxt = today + pd.offsets.MonthBegin(1)
        r = renewal(nxt.year, nxt.month)
    return max(1, (r - today).days)


def budget(remaining: float, base_per_day: float, today=None) -> float:
    """Credits extra markets may use today: what's left after the reserve and the daily odds for every remaining day
    before renewal, spread evenly over those days."""
    today = today if today is not None else pd.Timestamp.now(tz="America/New_York").tz_localize(None)
    days = days_to_renewal(today)
    spare = remaining - RESERVE - base_per_day * (days - 1)
    return max(0.0, spare / days)


# market key -> (group shown on the page, kind, unit)
# kinds: "ou" over/under, "yn" yes/no, "hcap" handicap (two sides), "all" every outcome listed, "one" one-sided
MARKETS = {
    "alternate_totals": ("Goals", "ou", "goals"),
    "team_totals": ("Goals", "ou", "goals"),
    "alternate_team_totals": ("Goals", "ou", "goals"),
    "totals_h1": ("Goals", "ou", "1st-half goals"),
    "btts": ("Goals", "yn", "Both teams to score"),
    "btts_h1": ("Goals", "yn", "Both teams to score in the 1st half"),
    "draw_no_bet": ("Result", "all", "draw no bet"),
    "h2h_h1": ("Result", "all", "1st half"),
    "double_chance": ("Result", "one", "double chance"),
    "halftime_fulltime": ("Result", "all", "half time / full time"),
    "alternate_spreads": ("Result", "hcap", "goals"),
    "correct_score": ("Result", "one", "correct score"),
    "alternate_totals_corners": ("Corners", "ou", "corners"),
    "alternate_spreads_corners": ("Corners", "hcap", "corners"),
    "alternate_team_totals_corners": ("Corners", "ou", "corners"),
    "corners_1x2": ("Corners", "all", "most corners"),
    "alternate_totals_cards": ("Cards", "ou", "cards"),
    "alternate_spreads_cards": ("Cards", "hcap", "cards"),
    "player_goal_scorer_anytime": ("Goalscorers", "one", "to score"),
    "player_first_goal_scorer": ("Goalscorers", "one", "to score first"),
    "player_last_goal_scorer": ("Goalscorers", "one", "to score last"),
    "player_shots_on_target": ("Player shots", "ou", "shots on target"),
    "player_shots_on_target_alternate": ("Player shots", "ou", "shots on target"),
    "player_shots": ("Player shots", "ou", "shots"),
    "player_shots_alternate": ("Player shots", "ou", "shots"),
    "player_assists": ("Player assists", "ou", "assists"),
    "player_assists_alternate": ("Player assists", "ou", "assists"),
    "player_to_receive_card": ("Player cards", "one", "to be booked"),
    "player_to_receive_red_card": ("Player cards", "one", "to be sent off"),
}
GROUPS = ["Result", "Goals", "Corners", "Cards", "Goalscorers", "Player shots", "Player assists", "Player cards"]


def due(raw: dict, now: pd.Timestamp | None = None, hours: int = WINDOW_HOURS) -> list[tuple[str, str]]:
    """(league key, event id) of the matches kicking off within `hours`, soonest first."""
    now = now or pd.Timestamp.now(tz="UTC")
    seen, out = set(), []
    for k, events in raw.items():
        if k.count("|") != 1:
            continue
        sport = k.split("|")[0]
        for ev in events:
            ko = pd.Timestamp(ev["commence_time"])
            if now < ko <= now + pd.Timedelta(hours=hours) and ev["id"] not in seen:
                seen.add(ev["id"])
                out.append((ko, sport, ev["id"]))
    return [(s, i) for _, s, i in sorted(out)]


def download(key: str, raw: dict, remaining, base_per_day: float = 60) -> tuple[dict, object, dict]:
    """Extra markets for today's matches, within today's share of the credits: ({event id: event odds}, credits left,
    a summary for the credits log). The biggest competitions go first."""
    out = {}
    try:
        left = float(remaining)
    except (TypeError, ValueError):
        left = 0
    cap = budget(left, base_per_day)
    info = {"extras_budget": round(cap), "extras_used": 0, "extras_matches": 0}
    if os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch":
        print("  extra markets skipped: run started by hand (only the morning run fetches them)")
        return out, remaining, info
    rank = lambda sport: PRIORITY.index(sport) if sport in PRIORITY else len(PRIORITY)
    todo = sorted(due(raw)[:MAX_EVENTS], key=lambda x: rank(x[0]))
    markets = ",".join(MARKETS)
    used, per_match = 0.0, FIRST_GUESS
    for sport, eid in todo:
        if used + per_match > cap:
            break
        url = (f"https://api.the-odds-api.com/v4/sports/{sport}/events/{eid}/odds?regions={REGIONS}"
               f"&markets={markets}&oddsFormat=decimal&apiKey={key}")
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                out[eid] = same_site(json.loads(r.read()))
                now_left = r.headers.get("x-requests-remaining", remaining)
        except Exception as e:
            print(f"  skipped extra markets for {eid}: {e}")
            continue
        try:
            used += float(remaining) - float(now_left)
        except (TypeError, ValueError):
            used += per_match
        remaining = now_left
        per_match = max(per_match, used / len(out))     # cautious: the dearest average so far
    info.update(extras_used=round(used), extras_matches=len(out))
    print(f"  extra markets: {len(out)} of {len(todo)} matches, {used:.0f} of {cap:.0f} credits allowed today")
    return out, remaining, info


def _label(market: str, name: str, desc: str | None, point, home: str, away: str) -> str:
    group, kind, unit = MARKETS[market]
    p = "" if point is None else f"{float(point):g}"
    if kind == "ou":
        who = f"{desc} " if desc else ""
        return f"{who}{name} {p} {unit}".replace("  ", " ")
    if kind == "yn":
        return f"{unit}: {name}"
    if kind == "hcap":
        return f"{name} {float(point):+g} {unit}" if point is not None else f"{name} {unit}"
    if kind == "one" and market.startswith("player_"):
        return f"{desc or name} {unit}"
    if market == "correct_score":
        return f"Correct score {name}"
    if market == "corners_1x2":
        return f"Most corners: {name}"
    return f"{name} ({unit})"


def table(extra: dict, sites: dict) -> pd.DataFrame:
    """One row per match, site, bet and outcome."""
    rows = []
    for eid, ev in extra.items():
        home, away = ev.get("home_team", ""), ev.get("away_team", "")
        for bk in ev.get("bookmakers", []):
            if bk["key"] not in sites:
                continue
            for mk in bk.get("markets", []):
                m = mk.get("key")
                if m not in MARKETS:
                    continue
                kind = MARKETS[m][1]
                for o in mk.get("outcomes", []):
                    name, desc, point = o.get("name", ""), o.get("description"), o.get("point")
                    if kind == "ou":
                        line = (desc or "", point)
                    elif kind == "hcap":   # the two sides of a handicap: home at -x and away at +x
                        hp = None if point is None else (point if name == home else -point)
                        line = ("", hp)
                    elif kind == "one":
                        line = (desc or "", point, name)
                    else:
                        line = (desc or "", None)
                    rows.append({"id": eid, "market": m, "group": MARKETS[m][0], "kind": kind,
                                 "line": json.dumps(line), "outcome": name, "site": bk["key"],
                                 "who": desc or "", "point": float(point) if point is not None else np.nan,
                                 "odds": float(after_fees(bk["key"], o["price"])),
                                 "label": _label(m, name, desc, point, home, away)})
    t = pd.DataFrame(rows)
    return t.drop_duplicates(["id", "market", "line", "outcome", "site"]).reset_index(drop=True) if len(t) else t


def price(t: pd.DataFrame, min_sites: int = 2) -> pd.DataFrame:
    """Adds chance, edge and best to every row. chance and edge are NaN where no expected chance exists."""
    if t is None or not len(t):
        return pd.DataFrame()
    t = t.copy()
    t["chance"], t["edge"] = np.nan, np.nan
    for (mid, m, line), g in t.groupby(["id", "market", "line"], sort=False):
        kind = g["kind"].iloc[0]
        if kind == "one":
            continue
        outs = sorted(g["outcome"].unique())
        if len(outs) < 2:
            continue
        W = g.pivot_table(index="site", columns="outcome", values="odds", aggfunc="first").reindex(columns=outs)
        W = W.dropna()
        if len(W) < min_sites:
            continue
        P = _probs(W.to_numpy(float))
        ok = np.isfinite(P).all(1)
        if ok.sum() < min_sites:
            continue
        C = pool(np.log(P[ok])[:, None, :], np.ones(ok.sum()) / ok.sum(), 1.0)[0]
        chance = dict(zip(outs, C))
        idx = g.index[g["site"].isin(W.index[ok])]
        t.loc[idx, "chance"] = t.loc[idx, "outcome"].map(chance)
        t.loc[idx, "edge"] = t.loc[idx, "chance"] * t.loc[idx, "odds"] - 1
    t["best"] = t["odds"] == t.groupby(["id", "market", "line", "outcome"])["odds"].transform("max")
    return t
