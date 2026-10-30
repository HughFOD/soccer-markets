"""The homepage: this week's soccer odds across US sportsbooks and prediction markets.

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
.bet-why{font-size:14px;color:var(--ink2);margin-top:6px}.bet-why b{font-weight:600;color:var(--ink)}
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


def usd(x: float) -> str:
    """Expected return per $1 -> per $100 in dollars, e.g. -0.077 -> '−$7.70'."""
    v = 100 * x
    return f"−${-v:.2f}" if v < -0.005 else f"+${v:.2f}"


def _pct(x, d=1, sign=True):
    return f"{100 * x:+.{d}f}%" if sign else f"{100 * x:.{d}f}%"


TOP_N = 10      # bets listed per day
MIN_EDGE = 0.001  # a bet is listed only if its best price beats the fair (consensus) price by 0.1%+


def daily_picks(M: pd.DataFrame, quotes: pd.DataFrame, now: pd.Timestamp | None = None,
                totals: pd.DataFrame | None = None) -> list[tuple[str, list[dict]]]:
    """[(day label, [bet, ...])] for each day from today on, highest expected return first.

    A bet is one result of one match at its best price across the sites. Its expected chance is the
    consensus of all the sites with their cuts removed; its expected return is expected chance x decimal
    odds - 1. Only bets with a positive expected return are kept. Matches that have kicked off are left out.
    `totals` (from usbooks.price_totals) adds goals over/under bets, priced the same way.
    """
    has_totals = totals is not None and len(totals)
    if not len(M) or (not len(quotes) and not has_totals):
        return []
    now = now or pd.Timestamp.now(tz=ET)
    order = {k: i for i, k in enumerate(SITES)}
    rows = []
    if len(quotes):
        q = quotes.merge(M[["id", "kickoff", "home", "away", "league", "best_h", "best_d", "best_a",
                            "cons_h", "cons_d", "cons_a"]], on="id")
        q["ko"] = pd.to_datetime(q["kickoff"]).dt.tz_convert(ET)
        q = q[q["ko"] > now]
        q["best_odds"] = [r[f"best_{r['result']}"] for _, r in q.iterrows()]
        top = q[np.isclose(q["odds"], q["best_odds"])]           # every site offering the best price
        for (mid, res), g in top.groupby(["id", "result"], sort=False):
            g = g.sort_values("site", key=lambda c: c.map(order))
            r = g.iloc[0]
            edge = float(r["edge"])
            if not (MIN_EDGE < edge <= MAX_EDGE):
                continue
            team = r["home"] if res == "h" else r["away"] if res == "a" else None
            rows.append({"day": r["ko"].date(), "ko": r["ko"], "edge": edge, "odds": american(r["odds"]), "paid": 1 / float(r["odds"]),
                         "bet": f"{team} to win" if team else "Draw", "match": f"{r['home']} v {r['away']}",
                         "league": r["league"], "sites": [SITES[x][0] for x in g["site"]],
                         "chance": float(r[f"cons_{res}"])})
    if totals is not None and len(totals):
        g2 = totals.copy()
        g2["ko"] = pd.to_datetime(g2["kickoff"]).dt.tz_convert(ET)
        g2 = g2[(g2["ko"] > now) & g2["best"]]
        for (mid, point, side), g in g2.groupby(["id", "point", "side"], sort=False):
            g = g.sort_values("site", key=lambda c: c.map(order))
            r = g.iloc[0]
            edge = float(r["edge"])
            if not (MIN_EDGE < edge <= MAX_EDGE):
                continue
            rows.append({"day": r["ko"].date(), "ko": r["ko"], "edge": edge, "odds": american(r["odds"]),
                         "paid": 1 / float(r["odds"]), "bet": f"{side} {point:g} goals",
                         "match": f"{r['home']} v {r['away']}", "league": r["league"],
                         "sites": [SITES[x][0] for x in g["site"]], "chance": float(r["chance"])})
    out = []
    today = now.date()
    if not any(x["day"] == today for x in rows) and len(M):
        out.append(("Today", []))
    for day in sorted({x["day"] for x in rows}):
        bets = sorted((x for x in rows if x["day"] == day), key=lambda x: -x["edge"])[:TOP_N]
        label = "Today" if day == today else "Tomorrow" if (day - today).days == 1 else pd.Timestamp(day).strftime("%a %b %-d")
        out.append((label, bets))
    return out


def chance_pair(expected: float, paid: float) -> tuple[str, str]:
    """Both chances as percentages, with one decimal place when whole numbers would look the same."""
    a, b = f"{100 * expected:.0f}%", f"{100 * paid:.0f}%"
    return (a, b) if a != b else (f"{100 * expected:.1f}%", f"{100 * paid:.1f}%")


def days_html(days: list[tuple[str, list[dict]]]) -> str:
    e = html.escape
    when = lambda lab: lab.lower() if lab in ("Today", "Tomorrow") else "on " + e(lab)
    if not days:
        return ("<div class=empty>No bet beats what's expected on any match coming up. "
                "That happens on quiet days; check back after the next update.</div>")
    first = next((i for i, (_, b) in enumerate(days) if b), 0)      # open on the first day that has bets
    tabs = "".join(f'<button class=daytab data-day="{i}"{" aria-selected=true" if i == first else ""}>{e(lab)}'
                   f'<span>{len(b)}</span></button>' for i, (lab, b) in enumerate(days))
    panes = []
    for i, (lab, bets) in enumerate(days):
        items = "".join(f"""<li class=bet-row><span class=rank>{k}</span>
<div class=bet-main><div class=bet-what>{e(b['bet'])}</div>
<div class=bet-match>{e(b['match'])} · {e(b['league'])} · {b['ko'].strftime('%-I:%M %p')} ET</div>
<div class=bet-why>Expected to win <b>{chance_pair(b['chance'], b['paid'])[0]}</b> of the time, paid as if <b>{chance_pair(b['chance'], b['paid'])[1]}</b></div></div>
<div class=bet-where><div class=bet-odds>{b['odds'].replace('-', '−')}</div><div class=bet-site>{e(' or '.join(b['sites']))}</div></div>
<div class=bet-value><span class=edge>+${100 * b['edge']:.2f}</span><div class=bet-chance>expected per $100</div></div></li>"""
                        for k, b in enumerate(bets, 1))
        note = (f"<div class=empty>No bet beats what's expected {when(lab)}. "
                "Every site is charging its full cut, so every bet is expected to lose money.</div>" if not bets else
                "" if len(bets) >= 5 else
                f"<p class=few>Only {len(bets)} bet{'s' if len(bets) != 1 else ''} beat{'s' if len(bets) == 1 else ''} "
                f"what's expected {when(lab)}. The rest are expected to lose money, so they're left out.</p>")
        panes.append(f'<div class=daypane data-day="{i}"{" hidden" if i != first else ""}><h3 class=dayhead>{e(lab)}</h3>'
                     + (f'<ol class=bets>{items}</ol>' if bets else '') + f'{note}</div>')
    js = ("<script>document.querySelectorAll('.daytab').forEach(t=>t.addEventListener('click',()=>{"
          "document.querySelectorAll('.daytab').forEach(x=>x.removeAttribute('aria-selected'));t.setAttribute('aria-selected','true');"
          "document.querySelectorAll('.daypane').forEach(p=>p.hidden=p.dataset.day!==t.dataset.day)}));"
          "document.documentElement.classList.add('js')</script>")
    return f'<div class=daytabs role=tablist>{tabs}</div>{"".join(panes)}{js}'


def build(M: pd.DataFrame, quotes: pd.DataFrame, board: pd.DataFrame, R: dict | None, stamp: str, remaining=None,
          totals: pd.DataFrame | None = None) -> str:
    e = html.escape
    present = [s for s in SITES if len(quotes) and s in set(quotes["site"])]
    n_flags = int(sum(1 for f in M["flag"] if f)) if len(M) else 0

    # ---- today's best bets: per day, up to TOP_N results whose best price beats the fair price
    days = daily_picks(M, quotes, totals=totals)
    picks_html = days_html(days)

    # ---- which site pays the most
    brows = ""
    if len(board):
        top = max(board["best_share"].max(), 1e-9)
        for _, b in board.iterrows():
            brows += (f"<tr><td><b>{e(b['name'])}</b><br><span class=kind>{e(b['kind'])}</span></td><td class=n>{b['matches']}</td>"
                      f"<td class=n>{_pct(b['margin'], 1, False)}</td>"
                      f"<td class=n><span class=bar style='width:{60 * b['best_share'] / top:.0f}px'></span>{100 * b['best_share']:.0f}%</td>"
                      f"<td class=n>{usd(b['avg_edge'])}</td></tr>")
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
            body += ("<tr class=cons><td>Expected</td>" + "".join(
                f"<td class=n>{r[f'cons_us_{o}']} <small>({100 * r[f'cons_{o}']:.0f}%)</small></td>" for o in "hda") + "</tr>")
            blocks.append(f"""<div class=match><h4>{e(r['home'])} v {e(r['away'])} <small>· {_ko(r['kickoff'])}</small></h4>
<div class=tablewrap><table><tr><th>Site</th><th class=n>{e(r['home'])}</th><th class=n>Draw</th><th class=n>{e(r['away'])}</th></tr>{body}</table></div></div>""")
        nflag = int((G["flag"] != "").sum())
        leagues.append(f"<details class=league{' open' if not leagues else ''}><summary>{e(lg)} <span>· {len(G)} matches"
                       f"</span></summary>{''.join(blocks)}</details>")

    # ---- does it work (history)
    hist = ""
    cs = (R or {}).get("consensus")
    if cs:
        rr = {x["threshold"]: x for x in cs["rules"]}
        r2 = rr.get(0.02)
        hrows = "".join(f"<tr><td>Over {100 * x['threshold']:.0f}%</td><td class=n>{x['bets']:,}</td>"
                        f"<td class=n>{_pct(x['expected'])}</td><td class=n>{_pct(x['edge_vs_close'])}</td><td class=n>{100 * x['beat_close']:.0f}%</td></tr>"
                        for x in cs["rules"])
        hist = f"""<h2>Does beating what's expected hold up?</h2>
<p class=sub>A bet that beats what's expected could just be noise. The test is whether it still beats it at kick-off,
when every site has caught up with the news. Free historical odds from American sportsbooks and prediction markets
don't exist, so this test uses the same method on {len(cs['books'])} European bookmakers, {cs['seasons'][0][:4]} to {cs['seasons'][-1][-4:]}
({cs['matches']:,} matches), comparing each bet with the expected chance just before kick-off.</p>
<div class=tablewrap><table><tr><th>Bets with an expected return of</th><th class=n>Bets</th><th class=n>Expected return when found</th><th class=n>Expected return at kick-off</th><th class=n>Still ahead at kick-off</th></tr>{hrows}</table></div>
<p class=note>Bets with an expected return over 2% were still ahead at kick-off {100 * r2['beat_close']:.0f}% of the time, by {_pct(r2['edge_vs_close'], 1, False)} on average
(95% range {_pct(r2['lo'], 1, False)} to {_pct(r2['hi'], 1, False)}). Small gaps (under 1%) are mostly noise. Profit over a few hundred bets
is too noisy to judge either way, which is why the kick-off price is the better test. This is a study of pricing, not betting advice.</p>"""

    return f"""<!doctype html><html lang=en><head>{theme.HEAD}
{theme.meta("", "Today's Soccer Bets: bets that beat the odds", "Every morning: the soccer bets at FanDuel, DraftKings, BetMGM, Kalshi and Polymarket that pay more than their chance of winning deserves.")}
<style>{CSS}</style></head><body>
{theme.nav("week")}
<section class=hero><div class=wrap>
<p class=eyebrow>Updated every morning</p>
<h1>Bets that beat what's expected.</h1>
<p class=lede>Every morning: the soccer bets that pay more than their chance of winning deserves, from the Premier League, La Liga, Bundesliga, Serie A, Ligue 1 and the Championship.</p>
<div class=ctas><a class=btn href="#best">See today's bets</a><a class="btn ghost" href="research.html">How accurate are odds</a></div>
<p class=updated>Last updated {stamp}</p>
</div></section>

<section class=band><div class=wrap>
<div class=stats>
<div class=stat><div class=v>{len(M)}</div><div class=l>matches this week</div></div>
<div class=stat><div class=v>{len(present)}</div><div class=l>sportsbooks and prediction markets</div></div>
<div class=stat><div class=v>{sum(len(b) for _, b in days)}</div><div class=l>bets that beat what's expected</div></div>
<div class=stat><div class=v>{e(best_site)}</div><div class=l>pays closest to expected</div></div>
</div></div></section>

<section class=section id=best><div class=wrap>
<h2>Ranked by expected return.</h2>
<p class=sub>Each result's chance comes from the odds at every site, with each site's cut removed. A bet is listed when one site pays more than that chance deserves. The green number is the average profit per $100 if you made that bet many times. Bet the result shown, at the site shown, at those odds or better.</p>
{picks_html}
</div></section>

<section class=band><div class=wrap>
<h2>Which site comes closest.</h2>
<p class=sub>Listed by US market share. The cut is each site's built-in margin (lower is better). "Best price" is how often it has the top odds. "Expected return" is the average result of betting $100 on every result it prices.</p>
<div class=tablewrap><table><tr><th>Site</th><th class=n>Matches</th><th class=n>Cut</th><th class=n>Best price</th><th class=n>Expected return per $100</th></tr>{brows}</table></div>
</div></section>

<section class=section><div class=wrap>
<h2>Every match.</h2>
<p class=sub>+150 means a $100 bet wins $150; −200 means you bet $200 to win $100. The best price for each result is in green. The "Expected" row shows each result's expected chance and the odds that would exactly match it.</p>
{''.join(leagues)}
</div></section>

{('<section class=band><div class=wrap>' + hist + '</div></section>') if hist else ''}

<section class=section><div class=wrap>
<h2>How it works.</h2>
<p class=sub>Three steps, rerun every morning.</p>
<div class=cards>
<div class=card><h3>Collect the odds.</h3><p>From FanDuel, DraftKings and BetMGM, plus Kalshi and Polymarket, through The Odds API.</p></div>
<div class=card><h3>Work out what's expected.</h3><p>Each site's odds become chances with its cut removed, then are averaged with equal weight. That gives every result's expected chance.</p></div>
<div class=card><h3>Find the bets that beat it.</h3><p>A bet makes the list when a site's odds pay more than its chance deserves. Gaps over 25% are left out as likely stale or mistyped prices.</p></div>
</div>
</div></section>
{theme.footer()}
</body></html>"""
