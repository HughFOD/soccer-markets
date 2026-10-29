"""The homepage: this week's football odds across US sportsbooks and prediction markets.

Built by markets.weekly from the saved Odds API responses and output/results.json.
"""
from __future__ import annotations

import html
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from . import theme
from .fairprice import MAX_EDGE
from .usbooks import SITES, THRESHOLD, american

ET = ZoneInfo("America/New_York")
REPO_URL = "https://github.com/HughFOD/soccer-markets"

CSS = theme.CSS + """
.picks{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}
.pick{background:var(--bg2);border-radius:18px;padding:22px 22px 20px;display:flex;flex-direction:column;gap:4px}
.pick .meta{font-size:13px;color:var(--muted)}
.pick .m{font-size:19px;font-weight:600;line-height:1.25;letter-spacing:-.015em}
.pick .bet{margin-top:10px;font-size:15px;color:var(--ink2)}
.pick .bet b{display:block;font:700 30px/1.1 -apple-system,BlinkMacSystemFont,"SF Pro Display",sans-serif;color:var(--ink);letter-spacing:-.02em;margin:2px 0}
.pick .vs{font-size:14px;color:var(--muted)}
.edge{display:inline-block;background:var(--goodbg);color:var(--good);font-size:13px;font-weight:600;padding:3px 10px;border-radius:980px;margin-left:6px;vertical-align:middle}
.empty{background:var(--bg2);border-radius:18px;padding:22px;color:var(--muted)}
.daytabs{display:flex;gap:8px;overflow-x:auto;padding:2px 0 18px;scrollbar-width:none}.daytabs::-webkit-scrollbar{display:none}
.daytab{flex:none;font:inherit;font-size:15px;border:0;border-radius:980px;padding:8px 16px;background:var(--bg2);color:var(--ink);cursor:pointer;letter-spacing:-.01em}
.daytab span{margin-left:7px;color:var(--muted);font-size:13px}
.daytab[aria-selected=true]{background:var(--ink);color:var(--bg)}.daytab[aria-selected=true] span{color:inherit;opacity:.7}
html:not(.js) .daytabs{display:none}html:not(.js) .daypane{display:block!important;margin-bottom:28px}
.dayhead{display:none}html:not(.js) .dayhead{display:block}
.bets{list-style:none;margin:0;padding:0;background:var(--bg2);border-radius:18px;overflow:hidden}
.bet-row{display:grid;grid-template-columns:44px 1fr auto auto;gap:18px;align-items:center;padding:16px 22px;border-top:1px solid var(--hair)}
.bet-row:first-child{border-top:0}
.rank{font:700 22px -apple-system,BlinkMacSystemFont,"SF Pro Display",sans-serif;color:var(--muted);text-align:center}
.bet-row:first-child .rank{color:var(--blue)}
.bet-what{font-size:19px;font-weight:600;letter-spacing:-.015em;line-height:1.25}
.bet-match{font-size:14px;color:var(--muted);margin-top:2px}
.bet-where{text-align:right}.bet-odds{font:700 24px/1.1 -apple-system,BlinkMacSystemFont,"SF Pro Display",sans-serif;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.bet-site{font-size:14px;color:var(--link);font-weight:500}
.bet-value{text-align:right;min-width:116px}.bet-value .edge{margin:0}.bet-chance{font-size:13px;color:var(--muted);margin-top:4px}
.few{font-size:14px;color:var(--muted);margin:12px 4px 0}
@media (max-width:640px){.bet-row{grid-template-columns:30px 1fr auto;gap:4px 12px;padding:14px 16px}
  .rank{font-size:18px;grid-row:1/3}.bet-where{grid-column:3;grid-row:1}.bet-value{grid-column:2/4;grid-row:2;text-align:left;min-width:0;display:flex;gap:10px;align-items:center}
  .bet-main{grid-column:2;grid-row:1}.bet-chance{margin:0}.bet-what{font-size:17px}.bet-odds{font-size:20px}}
.bar{display:inline-block;height:6px;border-radius:3px;background:var(--blue);vertical-align:middle;margin-right:8px}
.kind{font-size:12px;color:var(--muted)}
details.league{background:var(--tile);border-radius:18px;margin:12px 0;overflow:hidden}
details.league>summary{cursor:pointer;padding:18px 56px 18px 22px;font-size:19px;font-weight:600;list-style:none;position:relative;letter-spacing:-.015em}
details.league>summary::-webkit-details-marker{display:none}
details.league>summary:after{content:"+";position:absolute;right:22px;top:50%;transform:translateY(-52%);font-weight:300;font-size:26px;color:var(--muted);line-height:1}
details.league[open]>summary:after{content:"−"}
details.league>summary span{color:var(--muted);font-weight:400;font-size:15px;margin-left:8px}
.match{padding:6px 22px 18px}
.match h4{margin:10px 0 8px;font-size:16px;font-weight:600}.match h4 small{color:var(--muted);font-weight:400;font-size:13px}
.match .tablewrap{background:var(--bg2);border-radius:12px}
.match th,.match td{padding:9px 12px}
.best{color:var(--good);font-weight:700}
td.best{background:var(--goodbg)}
.cons td{color:var(--muted)}
.note{font-size:14px;color:var(--muted);margin-top:14px}
"""


def _ko(ts) -> str:
    t = pd.Timestamp(ts).tz_convert(ET)
    return t.strftime("%a %b %-d, %-I:%M %p") + " ET"


def _pct(x, d=1, sign=True):
    return f"{100 * x:+.{d}f}%" if sign else f"{100 * x:.{d}f}%"


TOP_N = 10      # bets listed per day
MIN_EDGE = 0.001  # a bet is listed only if its best price beats the fair (consensus) price by 0.1%+


def daily_picks(M: pd.DataFrame, quotes: pd.DataFrame, now: pd.Timestamp | None = None) -> list[tuple[str, list[dict]]]:
    """[(day label, [bet, ...])] for each day from today on, best value first.

    A bet is one result of one match at its best price across the sites. Value is how much that
    price pays compared with the consensus fair price. Matches that have already kicked off are left out.
    """
    if not len(M) or not len(quotes):
        return []
    now = now or pd.Timestamp.now(tz=ET)
    q = quotes.merge(M[["id", "kickoff", "home", "away", "league", "best_h", "best_d", "best_a",
                        "cons_h", "cons_d", "cons_a"]], on="id")
    q["ko"] = pd.to_datetime(q["kickoff"]).dt.tz_convert(ET)
    q = q[q["ko"] > now]
    q["best_odds"] = [r[f"best_{r['result']}"] for _, r in q.iterrows()]
    top = q[np.isclose(q["odds"], q["best_odds"])]           # every site offering the best price
    order = {k: i for i, k in enumerate(SITES)}
    rows = []
    for (mid, res), g in top.groupby(["id", "result"], sort=False):
        g = g.sort_values("site", key=lambda c: c.map(order))
        r = g.iloc[0]
        edge = float(r["edge"])
        if not (MIN_EDGE < edge <= MAX_EDGE):
            continue
        team = r["home"] if res == "h" else r["away"] if res == "a" else None
        rows.append({"day": r["ko"].date(), "ko": r["ko"], "edge": edge, "odds": american(r["odds"]),
                     "bet": f"{team} to win" if team else "Draw", "match": f"{r['home']} v {r['away']}",
                     "league": r["league"], "sites": [SITES[x][0] for x in g["site"]],
                     "chance": float(r[f"cons_{res}"])})
    out = []
    today = now.date()
    if not any(x["day"] == today for x in rows) and len(M):
        out.append(("Today", []))
    for day in sorted({x["day"] for x in rows}):
        bets = sorted((x for x in rows if x["day"] == day), key=lambda x: -x["edge"])[:TOP_N]
        label = "Today" if day == today else "Tomorrow" if (day - today).days == 1 else pd.Timestamp(day).strftime("%a %b %-d")
        out.append((label, bets))
    return out


def days_html(days: list[tuple[str, list[dict]]]) -> str:
    e = html.escape
    when = lambda lab: lab.lower() if lab in ("Today", "Tomorrow") else "on " + e(lab)
    if not days:
        return ("<div class=empty>No price beats the fair price on any match coming up. "
                "That happens on quiet days; check back after the next update.</div>")
    first = next((i for i, (_, b) in enumerate(days) if b), 0)      # open on the first day that has bets
    tabs = "".join(f'<button class=daytab data-day="{i}"{" aria-selected=true" if i == first else ""}>{e(lab)}'
                   f'<span>{len(b)}</span></button>' for i, (lab, b) in enumerate(days))
    panes = []
    for i, (lab, bets) in enumerate(days):
        items = "".join(f"""<li class=bet-row><span class=rank>{k}</span>
<div class=bet-main><div class=bet-what>{e(b['bet'])}</div>
<div class=bet-match>{e(b['match'])} · {e(b['league'])} · {b['ko'].strftime('%-I:%M %p')} ET</div></div>
<div class=bet-where><div class=bet-odds>{b['odds'].replace('-', '−')}</div><div class=bet-site>{e(' or '.join(b['sites']))}</div></div>
<div class=bet-value><span class=edge>{_pct(b['edge'])}</span><div class=bet-chance>{100 * b['chance']:.0f}% fair chance</div></div></li>"""
                        for k, b in enumerate(bets, 1))
        note = (f"<div class=empty>No price beats the fair price {when(lab)}. "
                "Every site is charging its full cut, so there's nothing worth backing.</div>" if not bets else
                "" if len(bets) >= 5 else
                f"<p class=few>Only {len(bets)} price{'s' if len(bets) != 1 else ''} beat{'s' if len(bets) == 1 else ''} "
                f"the fair price {when(lab)}. The rest pay less than fair, so they're left out.</p>")
        panes.append(f'<div class=daypane data-day="{i}"{" hidden" if i != first else ""}><h3 class=dayhead>{e(lab)}</h3>'
                     + (f'<ol class=bets>{items}</ol>' if bets else '') + f'{note}</div>')
    js = ("<script>document.querySelectorAll('.daytab').forEach(t=>t.addEventListener('click',()=>{"
          "document.querySelectorAll('.daytab').forEach(x=>x.removeAttribute('aria-selected'));t.setAttribute('aria-selected','true');"
          "document.querySelectorAll('.daypane').forEach(p=>p.hidden=p.dataset.day!==t.dataset.day)}));"
          "document.documentElement.classList.add('js')</script>")
    return f'<div class=daytabs role=tablist>{tabs}</div>{"".join(panes)}{js}'


def build(M: pd.DataFrame, quotes: pd.DataFrame, board: pd.DataFrame, R: dict | None, stamp: str, remaining=None) -> str:
    e = html.escape
    present = [s for s in SITES if len(quotes) and s in set(quotes["site"])]
    n_flags = int(sum(1 for f in M["flag"] if f)) if len(M) else 0

    # ---- today's best bets: per day, up to TOP_N results whose best price beats the fair price
    days = daily_picks(M, quotes)
    picks_html = days_html(days)

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
        leagues.append(f"<details class=league{' open' if not leagues else ''}><summary>{e(lg)} <span>· {len(G)} matches"
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

    return f"""<!doctype html><html lang=en><head>{theme.HEAD}
<title>Football Odds Compared</title>
<meta name=description content="This week's football odds at FanDuel, DraftKings, Fanatics, BetMGM, Caesars, Kalshi and Polymarket, compared with the consensus of all of them.">
<style>{CSS}</style></head><body>
{theme.nav("week")}
<section class=hero><div class=wrap>
<p class=eyebrow>Updated every morning</p>
<h1>The best bets, every day.</h1>
<p class=lede>The best-value bets for every day, from every match in six top leagues, priced by {', '.join(SITES[s][0] for s in present[:-1])}{' and ' + SITES[present[-1]][0] if present else ''}.</p>
<div class=ctas><a class=btn href="#best">See today's best bets</a><a class="btn ghost" href="research.html">How accurate are odds</a></div>
<p class=updated>Last updated {stamp}</p>
</div></section>

<section class=band><div class=wrap>
<div class=stats>
<div class=stat><div class=v>{len(M)}</div><div class=l>matches this week</div></div>
<div class=stat><div class=v>{len(present)}</div><div class=l>sportsbooks and prediction markets</div></div>
<div class=stat><div class=v>{n_flags}</div><div class=l>prices {THRESHOLD:.0%}+ better than consensus</div></div>
<div class=stat><div class=v>{e(best_site)}</div><div class=l>best prices on average</div></div>
</div></div></section>

<section class=section id=best><div class=wrap>
<h2>Ranked, day by day.</h2>
<p class=sub>Each day's bets where one site pays more than the fair price, ranked by value. Back the result shown, at the site shown, at those odds or better. The green figure is how much more it pays than fair.</p>
{picks_html}
</div></section>

<section class=band><div class=wrap>
<h2>Which site pays the most.</h2>
<p class=sub>Listed by US market share. The margin is each site's built-in cut (lower is better). "Best price" is how often it has the top odds. "Vs consensus" is how much it pays compared with the fair price.</p>
<div class=tablewrap><table><tr><th>Site</th><th class=n>Matches</th><th class=n>Margin</th><th class=n>Best price</th><th class=n>Vs consensus</th><th class=n>Flags</th></tr>{brows}</table></div>
</div></section>

<section class=section><div class=wrap>
<h2>Every match.</h2>
<p class=sub>+150 means a $100 bet wins $150; −200 means you bet $200 to win $100. The best price for each result is in green, and the consensus row shows the fair odds and chance.</p>
{''.join(leagues)}
</div></section>

{('<section class=band><div class=wrap>' + hist + '</div></section>') if hist else ''}

<section class=section><div class=wrap>
<h2>How it works.</h2>
<p class=sub>Three steps, rerun every week.</p>
<div class=cards>
<div class=card><h3>Collect the odds.</h3><p>From FanDuel, DraftKings, Fanatics, BetMGM and Caesars, plus Kalshi and Polymarket, through The Odds API. Caesars and Fanatics appear only on a paid data plan.</p></div>
<div class=card><h3>Build the consensus.</h3><p>Each site's odds become chances with its cut removed, then are averaged with equal weight. No site counts more than another.</p></div>
<div class=card><h3>Flag the gaps.</h3><p>A price more than {THRESHOLD:.0%} better than the consensus is flagged. Gaps over 25% are ignored as stale or mistyped prices.</p></div>
</div>
</div></section>
{theme.footer()}
</body></html>"""
