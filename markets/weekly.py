"""This week's fair prices: price every upcoming match and flag out-of-line bookmaker prices.

Run (needs internet for the fixtures file):  python -m markets.weekly
Writes output/this_week.csv and docs/this-week.html.
"""
from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from . import data, fairprice
from .report import BOOK_NAMES
from .website import CSS

ROOT = Path(__file__).resolve().parent.parent
LEAGUE_NAMES = {"E0": "Premier League", "E1": "Championship", "E2": "League One", "E3": "League Two",
                "SP1": "La Liga", "D1": "Bundesliga", "I1": "Serie A", "F1": "Ligue 1", "N1": "Eredivisie",
                "P1": "Primeira Liga", "SC0": "Scottish Premiership", "B1": "Belgian Pro League", "T1": "Süper Lig",
                "G1": "Greek Super League", "SP2": "La Liga 2", "D2": "2. Bundesliga", "I2": "Serie B", "F2": "Ligue 2"}


def page(tab: pd.DataFrame, weights: dict, stamp: str, threshold: float) -> str:
    flagged = tab[tab["flag"] != ""] if len(tab) else tab
    rows = []
    for _, r in tab.iterrows():
        cells = []
        for o in ("h", "d", "a"):
            e = r[f"edge_{o}"]
            hot = " class='num hot'" if threshold < e <= fairprice.MAX_EDGE else " class=num"
            cells.append(f"<td{hot}>{r[f'fair_odds_{o}']:.2f}<br><small>{100 * r[f'fair_{o}']:.0f}% · best {r[f'best_{o}']:.2f} {html.escape(BOOK_NAMES.get(r[f'best_book_{o}'], r[f'best_book_{o}']))}</small></td>")
        when = pd.Timestamp(r["date"]).strftime("%a %d %b") + (f" {r['time']}" if isinstance(r.get("time"), str) else "")
        rows.append(f"<tr><td>{when}<br><small>{html.escape(LEAGUE_NAMES.get(r['league'], r['league']))}</small></td>"
                    f"<td>{html.escape(r['home'])} v {html.escape(r['away'])}</td>{''.join(cells)}</tr>")
    wtxt = ", ".join(f"{BOOK_NAMES.get(k, k)} {100 * v / sum(weights.values()):.0f}%" for k, v in sorted(weights.items(), key=lambda kv: -kv[1]))
    css = CSS + ".hot{background:#fff1e8;color:#9a3a10;font-weight:600}td small{color:var(--muted);font-weight:400}.tablewrap{overflow-x:auto}"
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>This Week's Fair Prices</title>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700&family=Instrument+Sans:wght@400;500;600&family=JetBrains+Mono:wght@500;600&display=swap" rel=stylesheet>
<style>{css}</style></head><body>
<header class=hero><div class=wrap>
<div class=kicker>Fair-price engine · European bookmakers · updated {stamp}</div>
<h1>This Week's Fair Prices</h1>
<p class=lede>Fair odds for {len(tab)} upcoming matches, built from {int(tab['n_books'].median()) if len(tab) else 0} bookmakers per match. {f"{len(flagged)} have a bookmaker price at least {threshold:.0%} better than fair (highlighted)." if len(flagged) else f"No bookmaker price is {threshold:.0%} or more better than fair right now."}</p>
<p class=note>Covers the leagues the engine was tested on ({', '.join(sorted({LEAGUE_NAMES.get(x, x) for x in tab['league']})) if len(tab) else 'none this week'}). Each cell shows the fair odds, the fair chance, and the best price from a regular bookmaker. Weights: {wtxt}. <a href="index.html" style="color:#9fb4d4">How it works and its track record</a>.</p>
</div></header>
<main class=wrap><div class=tablewrap><table>
<tr><th>When</th><th>Match</th><th class=num>Home</th><th class=num>Draw</th><th class=num>Away</th></tr>
{''.join(rows)}
</table></div>
<p style="color:var(--muted);font-size:.9rem">Odds from football-data.co.uk, collected twice a week, so prices may have moved. This is a study of pricing, not betting advice.</p>
</main></body></html>"""


def us_page(tab: pd.DataFrame, stamp: str, threshold: float, remaining) -> str:
    """This week's prices at American sportsbooks."""
    from zoneinfo import ZoneInfo
    flagged = tab[tab["flag"] != ""] if len(tab) else tab
    rows = []
    for _, r in tab.iterrows():
        cells = []
        for o in ("h", "d", "a"):
            e = r.get(f"edge_{o}", np.nan)
            hot = " class='num hot'" if (np.isfinite(e) and threshold < e <= fairprice.MAX_EDGE) else " class=num"
            best = (f"best {r[f'best_us_{o}']} {html.escape(str(r[f'best_book_{o}']))}" if r[f"best_us_{o}"] else "no US price")
            cells.append(f"<td{hot}>{r[f'fair_us_{o}']}<br><small>{100 * r[f'fair_{o}']:.0f}% · {best}</small></td>")
        ko = pd.Timestamp(r["kickoff"]).tz_convert(ZoneInfo("America/New_York"))
        rows.append(f"<tr><td>{ko.strftime('%a %d %b, %-I:%M %p')} ET<br><small>{html.escape(r['league'])}</small></td>"
                    f"<td>{html.escape(r['home'])} v {html.escape(r['away'])}</td>{''.join(cells)}</tr>")
    flag_list = "".join(f"<li><b>{html.escape(r['home'])} v {html.escape(r['away'])}</b>: {html.escape(r['flag'])}</li>" for _, r in flagged.iterrows())
    css = CSS + ".hot{background:#fff1e8;color:#9a3a10;font-weight:600}td small{color:var(--muted);font-weight:400}.tablewrap{overflow-x:auto}"
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>This Week's Fair Prices</title>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700&family=Instrument+Sans:wght@400;500;600&family=JetBrains+Mono:wght@500;600&display=swap" rel=stylesheet>
<style>{css}</style></head><body>
<header class=hero><div class=wrap>
<div class=kicker>Fair-price engine · American sportsbooks · updated {stamp}</div>
<h1>This Week's Fair Prices</h1>
<p class=lede>Fair odds for {len(tab)} upcoming matches, compared with DraftKings, FanDuel, BetMGM, BetRivers and the other US-licensed sportsbooks. {(f"{len(flagged)} {'match has' if len(flagged) == 1 else 'matches have'} a sportsbook price at least {threshold:.0%} better than fair (highlighted).") if len(flagged) else f"No American sportsbook price is {threshold:.0%} or more better than fair right now."}</p>
<p class=note>Each cell shows the fair odds in American format, the fair chance, and the best American sportsbook price. The fair price blends the bookmakers' odds with their margins removed; betting exchanges are left out. Odds from The Odds API. <a href="index.html" style="color:#9fb4d4">How it works and its track record</a>.</p>
</div></header>
<main class=wrap>
{f"<h2>Flagged prices</h2><ul>{flag_list}</ul>" if flag_list else ""}
<div class=tablewrap><table>
<tr><th>Kick-off</th><th>Match</th><th class=num>Home</th><th class=num>Draw</th><th class=num>Away</th></tr>
{''.join(rows)}
</table></div>
<p style="color:var(--muted);font-size:.9rem"><b>Note on the track record.</b> The engine was tested on European bookmakers from 2013 to 2026, because free historical odds from American sportsbooks do not exist. This page applies the same method to American sportsbooks; how well it does on them will only be known as their prices are tracked over time. Prices move, so check before acting. This is a study of pricing, not betting advice.</p>
</main></body></html>"""


def run(raw_dir: Path = ROOT / "data" / "raw", fixtures: Path | None = None, out_dir: Path = ROOT / "output",
        docs: Path = ROOT / "docs", threshold: float = 0.02, download: bool = True) -> pd.DataFrame:
    from . import usbooks
    key = usbooks.api_key()
    from zoneinfo import ZoneInfo
    stamp = datetime.now(ZoneInfo("America/New_York")).strftime("%a %-d %b %Y, %-I:%M %p ET")
    if key or (ROOT / "data" / "us_odds.json").exists():
        from . import site
        path = ROOT / "data" / "us_odds.json"
        if key and download:
            fresh = usbooks.download(key, path.with_suffix(".new.json"))
            if not sum(len(v) for v in fresh.values()):
                # nothing came back (network or key problem): keep the last good odds and pages
                path.with_suffix(".new.json").unlink(missing_ok=True)
                raise SystemExit("No odds downloaded, so the pages were left as they were.")
            path.with_suffix(".new.json").replace(path)
        saved = json.loads(path.read_text())
        t = usbooks.to_table(saved["data"])
        M, quotes = usbooks.price(t, threshold)
        T = usbooks.totals_table(saved["data"])
        G = usbooks.price_totals(T, min_sites=2)
        if len(T):
            per = T.groupby(["id", "point"])["site"].nunique().value_counts().sort_index().to_dict()
            print(f"goals odds: {len(T)} prices from {sorted(T['site'].unique())}; sites per match line {per}; "
                  f"{G['id'].nunique() if len(G) else 0} matches priced")
        else:
            print("goals odds: none returned")
        from . import extras
        X = extras.price(extras.table(saved.get("extras") or {}, usbooks.SITES))
        if len(X):
            print(f"extra markets: {X['id'].nunique()} matches, {X.groupby(['id', 'market', 'line', 'outcome']).ngroups} bets, "
                  f"{int(X['edge'].notna().sum())} prices with an expected chance; groups {X['group'].value_counts().to_dict()}")
        board = usbooks.scoreboard(quotes, t)
        res = out_dir / "results.json"
        R = json.loads(res.read_text()) if res.exists() else None
        out_dir.mkdir(parents=True, exist_ok=True)
        M.to_csv(out_dir / "this_week_us.csv", index=False)
        board.to_csv(out_dir / "site_scoreboard.csv", index=False)
        # track record: save today's listed bets, re-check earlier ones, settle finished matches
        from . import track
        now = pd.Timestamp.now(tz=site.ET)
        days = site.daily_picks(M, quotes, now=now, totals=G, extras=X)
        L = track.load()
        L = track.record(L, days, now)
        L = track.update(L, site.daily_picks(M, quotes, now=now, totals=G, extras=X, everything=True), now)
        need = track.sports_needed(L, now)
        if key and download and need:
            L = track.grade(L, track.fetch_scores(key, need), now)
        else:
            L = track.grade(L, {}, now)
        track.save(L)
        print(f"track record: {len(L)} bets saved, {int(L['result'].isin(['won', 'lost', 'push', 'half won', 'half lost']).sum())} settled")
        page_html = site.build(M, quotes, board, R, stamp, saved.get("remaining"), totals=G, extras=X,
                               record_html=track.html_section(L))
        for name in ("index.html", "this-week.html"):
            (docs / name).write_text(page_html)
        from . import prices
        (docs / "best-prices.html").write_text(prices.build(M, quotes, G, stamp, extras=X))
        print(f"{len(M)} matches across {board.shape[0]} sites, {int((M['flag'] != '').sum()) if len(M) else 0} flagged -> docs/index.html")
        return M
    print("No Odds API key (odds_api_key.txt), so pricing against European bookmakers from football-data.co.uk instead.")
    fixtures = fixtures or ROOT / "data" / "fixtures.csv"
    if download:
        data.download_fixtures(fixtures)
        print(f"downloaded {fixtures.name}")
    m = data.load(raw_dir)
    books = fairprice.books_in(m)
    fx = data.load_fixtures(fixtures, leagues=tuple(m["league"].unique()))  # only leagues the engine was tested on
    weights = fairprice.latest_weights(m, books, available=fairprice.books_in(fx))
    tab = fairprice.this_week(fx, weights, threshold)
    out_dir.mkdir(parents=True, exist_ok=True)
    tab.to_csv(out_dir / "this_week.csv", index=False)
    stamp = datetime.now().strftime("%d %b %Y")
    (docs / "this-week.html").write_text(page(tab, weights, stamp, threshold))
    print(f"{len(tab)} matches priced, {int((tab['flag'] != '').sum()) if len(tab) else 0} with a flagged price -> docs/this-week.html")
    return tab


if __name__ == "__main__":
    run()
