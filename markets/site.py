"""The homepage: this week's football odds across US sportsbooks and prediction markets.

Built by markets.weekly from the saved Odds API responses and output/results.json.
"""
from __future__ import annotations

import html
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .usbooks import SITES, THRESHOLD, american

ET = ZoneInfo("America/New_York")
REPO_URL = "https://github.com/HughFOD/soccer-markets"

CSS = """
:root{--bg:#f7f6f2;--ink:#121418;--ink2:#454a54;--muted:#7a7f88;--line:#e2e0da;--card:#fff;--accent:#1f6fd1;--good:#0f7b4f;--goodbg:#e6f4ec;--hero:#0e1520;--heroink:#eef1f6}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#111317;--ink:#eceef2;--ink2:#b9bdc6;--muted:#8a8f99;--line:#2a2e35;--card:#191c21;--accent:#4b93ea;--good:#4cc38a;--goodbg:#173326;--hero:#0a0e14}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 'Instrument Sans',system-ui,sans-serif}
.wrap{max-width:1040px;margin:0 auto;padding:0 16px}
header{background:var(--hero);color:var(--heroink);padding:44px 0 64px}
.kicker{font:500 12px/1 'JetBrains Mono',monospace;letter-spacing:.12em;text-transform:uppercase;color:#9fb4d4}
h1{font:700 clamp(1.6rem,3.2vw,2.4rem)/1.15 Archivo,system-ui,sans-serif;margin:12px 0 14px;letter-spacing:-.01em;max-width:820px}
.lede{font-size:1.06rem;color:#cfd6e2;max-width:760px;margin:0}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line);border-radius:12px;overflow:hidden;margin:-36px 0 8px;position:relative}
.stat{background:var(--card);padding:16px 18px}.stat .v{font:700 1.45rem/1.15 Archivo,sans-serif}.stat .l{font-size:.82rem;color:var(--muted);margin-top:4px}
h2{font:700 1.35rem/1.25 Archivo,sans-serif;margin:44px 0 6px}
.sub{color:var(--ink2);margin:0 0 14px;max-width:780px}
.picks{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.pick{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--good);border-radius:10px;padding:14px 16px}
.pick .m{font-weight:600}.pick .meta{font-size:.82rem;color:var(--muted)}
.pick .bet{margin-top:8px;font:600 1.05rem 'JetBrains Mono',monospace}
.pick .vs{font-size:.88rem;color:var(--ink2)}
.edge{display:inline-block;background:var(--goodbg);color:var(--good);font:600 .8rem 'JetBrains Mono',monospace;padding:2px 7px;border-radius:6px;margin-left:6px}
.empty{background:var(--card);border:1px dashed var(--line);border-radius:10px;padding:16px;color:var(--ink2)}
table{border-collapse:collapse;width:100%;font-size:.92rem}
th,td{padding:7px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{color:var(--muted);font-weight:600;font-size:.8rem}
td.n,th.n{text-align:right;font-family:'JetBrains Mono',monospace}
.tablewrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:10px}
.bar{display:inline-block;height:8px;border-radius:4px;background:var(--accent);vertical-align:middle;margin-right:6px}
details{background:var(--card);border:1px solid var(--line);border-radius:10px;margin:10px 0}
summary{cursor:pointer;padding:12px 16px;font-weight:600}
summary span{color:var(--muted);font-weight:400}
.match{padding:6px 16px 14px;border-top:1px solid var(--line)}
.match h4{margin:8px 0 4px;font:600 .98rem Archivo,sans-serif}.match h4 small{color:var(--muted);font-weight:400}
.best{background:var(--goodbg);color:var(--good);font-weight:700}
.cons td{color:var(--ink2);font-style:italic}
.kind{font-size:.75rem;color:var(--muted)}
.note{font-size:.88rem;color:var(--ink2)}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px}.card h3{margin:0 0 6px;font:650 1rem Archivo,sans-serif}.card p{margin:0;color:var(--ink2);font-size:.92rem}
a{color:var(--accent)}footer{border-top:1px solid var(--line);margin-top:48px;padding:22px 0 36px;color:var(--muted);font-size:.88rem}
@media (max-width:760px){.stats{grid-template-columns:repeat(2,1fr)}.cards{grid-template-columns:1fr}}
"""


def _ko(ts) -> str:
    t = pd.Timestamp(ts).tz_convert(ET)
    return t.strftime("%a %b %-d, %-I:%M %p") + " ET"


def _pct(x, d=1, sign=True):
    return f"{100 * x:+.{d}f}%" if sign else f"{100 * x:.{d}f}%"


def build(M: pd.DataFrame, quotes: pd.DataFrame, board: pd.DataFrame, R: dict | None, stamp: str, remaining=None) -> str:
    e = html.escape
    present = [s for s in SITES if len(quotes) and s in set(quotes["site"])]
    n_flags = int(sum(1 for f in M["flag"] if f)) if len(M) else 0

    # ---- best prices right now
    picks = []
    for _, r in M.iterrows():
        for o, lab in zip("hda", ("home win", "draw", "away win")):
            ed = r[f"edge_{o}"]
            if THRESHOLD < ed <= 0.25:
                team = r["home"] if o == "h" else r["away"] if o == "a" else "Draw"
                what = f"{team} to win" if o != "d" else "Draw"
                picks.append((ed, f"""<div class=pick><div class=m>{e(r['home'])} v {e(r['away'])}</div>
<div class=meta>{e(r['league'])} · {_ko(r['kickoff'])}</div>
<div class=bet>{e(what)} {r[f'best_us_{o}']} <span class=vs>at {e(r[f'best_site_{o}'])}</span><span class=edge>{_pct(ed)}</span></div>
<div class=vs>Consensus {r[f'cons_us_{o}']} ({100 * r[f'cons_{o}']:.0f}% chance)</div></div>"""))
    picks = "".join(p for _, p in sorted(picks, key=lambda x: -x[0]))
    picks_html = f"<div class=picks>{picks}</div>" if picks else (
        f"<div class=empty>No site is more than {THRESHOLD:.0%} better than the consensus on any result right now. "
        "Prices are usually close; gaps appear when one site is slow to move.</div>")

    # ---- which site pays the most
    brows = ""
    if len(board):
        top = max(board["best_share"].max(), 1e-9)
        for _, b in board.iterrows():
            brows += (f"<tr><td><b>{e(b['name'])}</b><br><span class=kind>{e(b['kind'])}</span></td><td class=n>{b['matches']}</td>"
                      f"<td class=n>{_pct(b['margin'], 1, False)}</td>"
                      f"<td class=n><span class=bar style='width:{60 * b['best_share'] / top:.0f}px'></span>{100 * b['best_share']:.0f}%</td>"
                      f"<td class=n>{_pct(b['avg_edge'])}</td><td class=n>{b['flagged']}</td></tr>")
    # best average price among sites quoting at least a quarter of the matches (so a site with a handful of prices can't win)
    big = board[board["matches"] >= 0.25 * board["matches"].max()] if len(board) else board
    best_site = big.loc[big["avg_edge"].idxmax(), "name"] if len(big) else "–"

    # ---- all matches, by league
    q = quotes.set_index(["id", "site", "result"])["odds"] if len(quotes) else pd.Series(dtype=float)
    leagues = []
    for lg, G in (M.groupby("league", sort=False) if len(M) else []):
        blocks = []
        for _, r in G.iterrows():
            sites = [s for s in SITES if s in r["sites"].split(",")]
            body = ""
            for s in sites:
                cells = ""
                for o in "hda":
                    v = q.get((r["id"], s, o), np.nan)
                    cls = " class='n best'" if np.isfinite(v) and v >= r[f"best_{o}"] - 1e-9 else " class=n"
                    cells += f"<td{cls}>{american(v)}</td>"
                body += f"<tr><td>{e(SITES[s][0])}</td>{cells}</tr>"
            body += ("<tr class=cons><td>Consensus</td>" + "".join(
                f"<td class=n>{r[f'cons_us_{o}']} <small>({100 * r[f'cons_{o}']:.0f}%)</small></td>" for o in "hda") + "</tr>")
            blocks.append(f"""<div class=match><h4>{e(r['home'])} v {e(r['away'])} <small>· {_ko(r['kickoff'])}</small></h4>
<div class=tablewrap><table><tr><th>Site</th><th class=n>{e(r['home'])}</th><th class=n>Draw</th><th class=n>{e(r['away'])}</th></tr>{body}</table></div></div>""")
        nflag = int((G["flag"] != "").sum())
        leagues.append(f"<details{' open' if not leagues else ''}><summary>{e(lg)} <span>· {len(G)} matches"
                       f"{f' · {nflag} flagged' if nflag else ''}</span></summary>{''.join(blocks)}</details>")

    # ---- does it work (history)
    hist = ""
    cs = (R or {}).get("consensus")
    if cs:
        rr = {x["threshold"]: x for x in cs["rules"]}
        r2 = rr.get(0.02)
        hrows = "".join(f"<tr><td>More than {100 * x['threshold']:.0f}% better</td><td class=n>{x['bets']:,}</td>"
                        f"<td class=n>{_pct(x['expected'])}</td><td class=n>{_pct(x['edge_vs_close'])}</td><td class=n>{100 * x['beat_close']:.0f}%</td></tr>"
                        for x in cs["rules"])
        hist = f"""<h2>Does beating the consensus mean anything?</h2>
<p class=sub>A price that beats the consensus could just be noise. The test is whether it still looks good at kick-off,
when every site has caught up with the news. Free historical odds from American sportsbooks and prediction markets
don't exist, so this test uses the same method on {len(cs['books'])} European bookmakers, {cs['seasons'][0][:4]} to {cs['seasons'][-1][-4:]}
({cs['matches']:,} matches), comparing each flagged price with the consensus closing price.</p>
<div class=tablewrap><table><tr><th>When a price beat the consensus by</th><th class=n>Prices</th><th class=n>Gap when flagged</th><th class=n>Gap at kick-off</th><th class=n>Still better at kick-off</th></tr>{hrows}</table></div>
<p class=note>Prices more than 2% better than the consensus were still better at kick-off {100 * r2['beat_close']:.0f}% of the time, by {_pct(r2['edge_vs_close'], 1, False)} on average
(95% range {_pct(r2['lo'], 1, False)} to {_pct(r2['hi'], 1, False)}). Small gaps (under 1%) are mostly noise. Profit over a few hundred bets
is too noisy to judge either way, which is why the kick-off price is the better test. This is a study of pricing, not betting advice.</p>"""

    return f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Football Odds Compared</title>
<meta name=description content="This week's football odds at FanDuel, DraftKings, Fanatics, BetMGM, Caesars, Kalshi and Polymarket, compared with the consensus of all of them.">
<link rel=preconnect href=https://fonts.googleapis.com><link rel=preconnect href=https://fonts.gstatic.com crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700&family=Instrument+Sans:wght@400;500;600&family=JetBrains+Mono:wght@500;600&display=swap" rel=stylesheet>
<style>{CSS}</style></head><body>
<header><div class=wrap>
<div class=kicker>Updated {stamp} · {len(M)} matches · {len(present)} sites</div>
<h1>Football Odds Compared Across US Sportsbooks and Prediction Markets</h1>
<p class=lede>Every match this week in six top leagues, priced by {', '.join(SITES[s][0] for s in present[:-1])}{' and ' + SITES[present[-1]][0] if present else ''}.
Each site's odds are compared with the consensus of all of them, and any price clearly better than the consensus is flagged.</p>
</div></header>
<main class=wrap>
<div class=stats>
<div class=stat><div class=v>{len(M)}</div><div class=l>matches this week</div></div>
<div class=stat><div class=v>{len(present)}</div><div class=l>sportsbooks and prediction markets</div></div>
<div class=stat><div class=v>{n_flags}</div><div class=l>matches with a price {THRESHOLD:.0%}+ better than consensus</div></div>
<div class=stat><div class=v>{e(best_site)}</div><div class=l>best prices on average this week</div></div>
</div>

<h2>Best prices right now</h2>
<p class=sub>Prices more than {THRESHOLD:.0%} better than the consensus. The percentage is how much more the bet pays than the consensus says it should.</p>
{picks_html}

<h2>Which site pays the most?</h2>
<p class=sub>Sites are listed by US market share, largest first. The consensus has every site's cut removed, so it is the fair price, and a site with a cut pays a little less than fair on most results. The margin is that cut (lower is better). "Best price" is how often a site has the top odds on a result. "Vs consensus" is how much its odds pay on average compared with fair.</p>
<div class=tablewrap><table><tr><th>Site</th><th class=n>Matches</th><th class=n>Margin</th><th class=n>Best price</th><th class=n>Vs consensus</th><th class=n>Flags</th></tr>{brows}</table></div>

<h2>All matches</h2>
<p class=sub>American odds: +150 means a $100 bet wins $150; −200 means you bet $200 to win $100. The best price for each result is highlighted. The consensus row shows the fair odds and chance.</p>
{''.join(leagues)}

{hist}

<h2>How it works</h2>
<div class=cards>
<div class=card><h3>1. Collect the odds</h3><p>Odds for every match come from The Odds API, limited to FanDuel, DraftKings, Fanatics, BetMGM and Caesars, plus Kalshi and Polymarket, listed by market share. Caesars and Fanatics appear only on a paid data plan.</p></div>
<div class=card><h3>2. Build the consensus</h3><p>Each site's odds are turned into chances with its cut removed, then averaged with equal weight. No site counts more than another.</p></div>
<div class=card><h3>3. Flag the gaps</h3><p>A price more than {THRESHOLD:.0%} better than the consensus is flagged. Gaps over 25% are ignored as stale or mistyped prices.</p></div>
</div>
<p class=note style="margin-top:14px">Prices move constantly, so check the site before acting. Odds from The Odds API; history from football-data.co.uk.
<a href="research.html">Background research on 50,000 matches</a> · <a href="{REPO_URL}">Code on GitHub</a></p>
</main>
<footer><div class=wrap>A data science project in Python by Hugh. This is a study of pricing, not betting advice.</div></footer>
</body></html>"""
