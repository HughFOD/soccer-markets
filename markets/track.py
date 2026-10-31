"""Track record: how the homepage's bets actually turned out.

Every morning (markets.weekly):
  1. record  - every bet the homepage lists is saved to data/track_record.csv, once, at the price
               and site first shown.
  2. update  - while the match is still to come, each saved bet is re-checked against the latest
               expected chance: would the price first shown still beat what's expected now? The last
               check before kick-off is the fairest test of whether a bet was really good value,
               because by then more news is in.
  3. grade   - after the match, the final score from The Odds API decides results, goals totals,
               handicaps, both-teams-to-score and draw-no-bet bets. Corners, cards and player bets
               need match statistics the scores don't include, so they are marked "not graded".

Profit assumes $100 on every bet at the price first shown.
"""
from __future__ import annotations

import html
import json
import urllib.request

import numpy as np
import pandas as pd

from .usbooks import ROOT, SPORTS, american

LEDGER = ROOT / "data" / "track_record.csv"
COLS = ["key", "flagged_at", "kickoff", "league", "id", "home", "away", "match", "bet", "kind", "outcome", "point",
        "sites", "n_sites", "odds", "chance", "edge", "last_checked", "last_chance", "last_value", "result", "profit"]
GRADABLE = {"result", "totals", "alternate_totals", "alternate_spreads", "btts", "draw_no_bet"}
SETTLE_HOURS = 2.5   # a match is treated as finished this long after kick-off
GIVE_UP_DAYS = 3     # the scores endpoint only looks back 3 days


def load() -> pd.DataFrame:
    if LEDGER.exists():
        L = pd.read_csv(LEDGER, dtype={"result": str, "outcome": str, "key": str, "id": str})
        L["result"] = L["result"].fillna("")
        return L
    return pd.DataFrame(columns=COLS)


def save(L: pd.DataFrame) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    L[COLS].to_csv(LEDGER, index=False)


def bet_key(b: dict) -> str:
    point = "" if b.get("point") is None or pd.isna(b.get("point")) else f"{float(b['point']):g}"
    return f"{b['id']}|{b['kind']}|{b['outcome']}|{point}"


def record(L: pd.DataFrame, days: list, now: pd.Timestamp) -> pd.DataFrame:
    """Add every listed bet not already in the ledger."""
    have = set(L["key"]) if len(L) else set()
    new = []
    for _, bets in days:
        for b in bets:
            k = bet_key(b)
            if k in have:
                continue
            have.add(k)
            home, away = b["match"].split(" v ", 1)
            new.append({"key": k, "flagged_at": now.isoformat(), "kickoff": pd.Timestamp(b["ko"]).isoformat(),
                        "league": b["league"], "id": b["id"], "home": home, "away": away, "match": b["match"],
                        "bet": b["bet"], "kind": b["kind"], "outcome": b["outcome"], "point": b.get("point"),
                        "sites": ", ".join(b["sites"]), "n_sites": b.get("n_sites"), "odds": b["dec"],
                        "chance": b["chance"], "edge": b["edge"], "last_checked": now.isoformat(),
                        "last_chance": b["chance"], "last_value": b["edge"], "result": "", "profit": np.nan})
    if not new:
        return L
    N = pd.DataFrame(new, columns=COLS)
    return N if not len(L) else pd.concat([L, N], ignore_index=True)


def update(L: pd.DataFrame, everything: list, now: pd.Timestamp) -> pd.DataFrame:
    """Re-check bets whose match hasn't started against the latest expected chance."""
    if not len(L):
        return L
    latest = {bet_key(b): b["chance"] for b in everything}
    ko = pd.to_datetime(L["kickoff"], utc=True)
    for i in L.index[(ko > now) & (L["result"] == "")]:
        c = latest.get(L.at[i, "key"])
        if c is None or not np.isfinite(c):
            continue
        L.at[i, "last_chance"] = c
        L.at[i, "last_value"] = c * float(L.at[i, "odds"]) - 1
        L.at[i, "last_checked"] = now.isoformat()
    return L


# ---- grading -------------------------------------------------------------------------------------

def _line(margin: float) -> int:
    """+1 win, 0 push (stake back), -1 loss, for a margin over the line."""
    return 1 if margin > 0 else 0 if margin == 0 else -1


def _asian(margin_at_zero: float, point: float) -> list[tuple[float, int]]:
    """Lines ending in .25 or .75 are two half-bets on the neighbouring lines; others are one bet."""
    if abs((point * 4) % 2) == 1:
        return [(0.5, _line(margin_at_zero + point - 0.25)), (0.5, _line(margin_at_zero + point + 0.25))]
    return [(1.0, _line(margin_at_zero + point))]


def settle(row, hg: int, ag: int) -> list[tuple[float, int]] | None:
    """[(share of stake, +1 win / 0 push / -1 loss), ...], or None if the score can't settle it."""
    kind, out = row["kind"], str(row["outcome"])
    point = float(row["point"]) if pd.notna(row["point"]) else 0.0
    if kind == "result":
        actual = "h" if hg > ag else "a" if ag > hg else "d"
        return [(1.0, 1 if out == actual else -1)]
    if kind in ("totals", "alternate_totals"):
        total = hg + ag
        if out == "Over":
            return _asian(total, -point)
        if out == "Under":
            return _asian(-total, point)
        return None
    if kind == "alternate_spreads":
        if out == row["home"]:
            return _asian(hg - ag, point)
        if out == row["away"]:
            return _asian(ag - hg, point)
        return None
    if kind == "btts":
        return [(1.0, 1 if (out == "Yes") == (hg > 0 and ag > 0) else -1)]
    if kind == "draw_no_bet":
        if hg == ag:
            return [(1.0, 0)]
        winner = row["home"] if hg > ag else row["away"]
        return [(1.0, 1 if out == winner else -1)]
    return None


def profit_and_label(parts: list[tuple[float, int]], odds: float, stake: float = 100.0) -> tuple[float, str]:
    profit = sum(stake * sh * ((odds - 1) if o == 1 else 0 if o == 0 else -1) for sh, o in parts)
    outs = {o for _, o in parts}
    label = ("won" if outs == {1} else "lost" if outs == {-1} else "push" if outs == {0}
             else "half won" if profit > 0 else "half lost")
    return round(profit, 2), label


def sports_needed(L: pd.DataFrame, now: pd.Timestamp) -> list[str]:
    if not len(L):
        return []
    ko = pd.to_datetime(L["kickoff"], utc=True)
    due = L[(L["result"] == "") & L["kind"].isin(GRADABLE) & (ko < now - pd.Timedelta(hours=SETTLE_HOURS))]
    names = {v: k for k, v in SPORTS.items()}
    return sorted({names[x] for x in due["league"] if x in names})


def fetch_scores(api_key: str, sports: list[str]) -> dict:
    """{event id: (home goals, away goals)} for completed matches in the last 3 days (2 credits per league)."""
    out = {}
    for sp in sports:
        url = f"https://api.the-odds-api.com/v4/sports/{sp}/scores/?daysFrom=3&apiKey={api_key}"
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                events = json.loads(r.read())
        except Exception as e:  # a failed league is retried tomorrow
            print(f"  scores for {sp} not available: {e}")
            continue
        for ev in events:
            if not ev.get("completed") or not ev.get("scores"):
                continue
            s = {x["name"]: x["score"] for x in ev["scores"]}
            try:
                out[ev["id"]] = (int(s[ev["home_team"]]), int(s[ev["away_team"]]))
            except (KeyError, TypeError, ValueError):
                continue
    return out


def grade(L: pd.DataFrame, scores: dict, now: pd.Timestamp) -> pd.DataFrame:
    if not len(L):
        return L
    ko = pd.to_datetime(L["kickoff"], utc=True)
    done = ko < now - pd.Timedelta(hours=SETTLE_HOURS)
    for i in L.index[done & (L["result"] == "")]:
        row = L.loc[i]
        if row["kind"] not in GRADABLE:
            L.at[i, "result"] = "not graded"
            continue
        if row["id"] in scores:
            parts = settle(row, *scores[row["id"]])
            if parts is None:
                L.at[i, "result"] = "not graded"
                continue
            L.at[i, "profit"], L.at[i, "result"] = profit_and_label(parts, float(row["odds"]))
        elif ko[i] < now - pd.Timedelta(days=GIVE_UP_DAYS):
            L.at[i, "result"] = "no score found"
    return L


# ---- page section ------------------------------------------------------------------------------------

def _usd(x: float) -> str:
    return f"{'+' if x >= 0 else '−'}${abs(x):,.0f}"


def html_section(L: pd.DataFrame) -> str:
    e = html.escape
    if not len(L):
        return ""
    start = pd.to_datetime(L["flagged_at"], utc=True).min().tz_convert("America/New_York")
    g = L[L["result"].isin(["won", "lost", "push", "half won", "half lost"])].copy()
    checked = L[pd.to_datetime(L["last_checked"], utc=True) > pd.to_datetime(L["flagged_at"], utc=True)]
    still = f"{100 * (checked['last_value'] > 0).mean():.0f}%" if len(checked) else "–"
    intro = (f"Every bet listed on this page since {start:%B %-d, %Y} is saved at the price first shown. "
             "Before kick-off it's checked again against the latest odds, and after the match it's settled "
             "from the final score. Profit assumes $100 on each bet.")
    if not len(g):
        return (f"<section class=section><div class=wrap><h2>How the picks have done.</h2><p class=sub>{intro}</p>"
                f"<p class=sub><b>{len(L)} bets recorded so far.</b> Results appear here once their matches finish."
                + (f" So far, <b>{still}</b> of the bets re-checked before kick-off were still good value." if len(checked) else "")
                + "</p></div></section>")
    n, profit = len(g), g["profit"].sum()
    w, lo = g["result"].isin(["won", "half won"]).sum(), g["result"].isin(["lost", "half lost"]).sum()
    pu = (g["result"] == "push").sum()
    tiles = (f"<div class=stats><div class=stat><div class=v>{n}</div><div class=l>bets settled</div></div>"
             f"<div class=stat><div class=v>{w}–{lo}{f'–{pu}' if pu else ''}</div><div class=l>won–lost{'–push' if pu else ''}</div></div>"
             f"<div class=stat><div class=v>{_usd(profit)}</div><div class=l>profit from $100 on each ({100 * profit / (100 * n):+.1f}%)</div></div>"
             f"<div class=stat><div class=v>{100 * g['edge'].mean():+.1f}%</div><div class=l>expected return when listed</div></div>"
             f"<div class=stat><div class=v>{still}</div><div class=l>still good value at the last check before kick-off</div></div></div>")
    recent = g.sort_values("kickoff", ascending=False).head(15)
    rows = "".join(
        f"<tr><td>{pd.Timestamp(r['kickoff']).tz_convert('America/New_York'):%b %-d}</td><td>{e(r['bet'])}<br><span class=kind>{e(r['match'])}</span></td>"
        f"<td>{e(str(r['sites']).split(',')[0])}</td><td class=n>{american(float(r['odds']))}</td>"
        f"<td class=n>{e(r['result'])}</td><td class=n>{_usd(float(r['profit']))}</td></tr>"
        for _, r in recent.iterrows())
    other = int((L["result"] == "not graded").sum())
    note = (f" {other} corners, cards or player bets aren't counted, because the final score alone can't settle them."
            if other else "")
    return (f"<section class=section><div class=wrap><h2>How the picks have done.</h2><p class=sub>{intro}</p>{tiles}"
            f"<p class=note>Wins and losses swing a lot over a few dozen bets, so the profit figure means little until there are "
            f"several hundred. The \"still good value\" share is the steadier test.{note}</p>"
            f"<div class=tablewrap><table><tr><th>Date</th><th>Bet</th><th>Site</th><th class=n>Odds</th><th class=n>Result</th>"
            f"<th class=n>Profit on $100</th></tr>{rows}</table></div></div></section>")
