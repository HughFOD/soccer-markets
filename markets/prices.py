"""Best prices page (docs/best-prices.html): for every upcoming match, the best odds and the site
offering them for each bet, with the expected return per $100 at that price.

Built by markets.weekly from the same data as the homepage.
"""
from __future__ import annotations

import html

import numpy as np
import pandas as pd

from . import theme
from .site import CSS, ET, _ko
from .usbooks import SITES, american

PAGE_CSS = """
.mlist{display:grid;gap:14px;grid-template-columns:minmax(0,1fr)}
.mcard{background:var(--bg2);border-radius:18px;padding:18px 22px 10px}
.mcard h3{font-size:19px;margin:0}.mcard .meta{font-size:13px;color:var(--muted);margin:2px 0 10px}
.mcard table{font-size:15px}.mcard th,.mcard td{padding:9px 6px}.mcard td.n,.mcard th.n{white-space:nowrap}
.mcard .odds{font-weight:700;font-variant-numeric:tabular-nums}
.mcard .site{display:block;color:var(--link);font-weight:500;font-size:13px}
.mcard .pos{color:var(--good);font-weight:700}.mcard .neg{color:var(--muted)}
.mcard .grp td{color:var(--muted);font-size:12px;font-weight:600;padding-top:14px;border-bottom:0;text-transform:uppercase;letter-spacing:.04em}
@media (max-width:520px){.mcard{padding:16px 14px 8px}.mcard table{font-size:14px}.mcard th,.mcard td{padding:8px 4px}}
"""


def _usd(x: float) -> str:
    v = 100 * x
    return f"−${-v:.2f}" if v < -0.005 else f"+${v:.2f}"


def _row(bet: str, odds: float, sites: list[str], edge: float) -> str:
    e = html.escape
    cls = "pos" if edge > 0 else "neg"
    return (f"<tr><td>{e(bet)}</td><td class=n><span class=odds>{american(odds).replace('-', '−')}</span>"
            f"<span class=site>{e(' / '.join(sites))}</span></td><td class='n {cls}'>{_usd(edge)}</td></tr>")


def matches_by_day(M: pd.DataFrame, quotes: pd.DataFrame, totals: pd.DataFrame | None,
                   now: pd.Timestamp | None = None) -> list[tuple[str, list[dict]]]:
    """[(day label, [match, ...])]; each match has its bets with the best odds and sites."""
    if not len(M):
        return []
    now = now or pd.Timestamp.now(tz=ET)
    order = {k: i for i, k in enumerate(SITES)}
    best = quotes[quotes["best"]] if len(quotes) else quotes
    tbest = totals[totals["best"]] if totals is not None and len(totals) else None
    out: dict = {}
    for _, r in M.iterrows():
        ko = pd.Timestamp(r["kickoff"]).tz_convert(ET)
        if ko <= now:
            continue
        bets = []
        for o, name in (("h", f"{r['home']} to win"), ("d", "Draw"), ("a", f"{r['away']} to win")):
            g = best[(best["id"] == r["id"]) & (best["result"] == o)].sort_values("site", key=lambda c: c.map(order))
            if len(g):
                bets.append(("Result", name, float(g["odds"].iloc[0]), [SITES[s][0] for s in g["site"]], float(g["edge"].iloc[0])))
        if tbest is not None:
            g2 = tbest[tbest["id"] == r["id"]]
            for (point, side), g in sorted(g2.groupby(["point", "side"]), key=lambda kv: (kv[0][0], kv[0][1] != "Over")):
                g = g.sort_values("site", key=lambda c: c.map(order))
                bets.append(("Goals", f"{side} {point:g} goals", float(g["odds"].iloc[0]),
                             [SITES[s][0] for s in g["site"]], float(g["edge"].iloc[0])))
        out.setdefault(ko.date(), []).append({"ko": ko, "home": r["home"], "away": r["away"], "league": r["league"], "bets": bets})
    today = now.date()
    res = []
    for day in sorted(out):
        label = "Today" if day == today else "Tomorrow" if (day - today).days == 1 else pd.Timestamp(day).strftime("%a %b %-d")
        res.append((label, sorted(out[day], key=lambda m: m["ko"])))
    return res


def build(M: pd.DataFrame, quotes: pd.DataFrame, totals: pd.DataFrame | None, stamp: str) -> str:
    e = html.escape
    days = matches_by_day(M, quotes, totals)
    tabs = "".join(f'<button class=daytab data-day="{i}"{" aria-selected=true" if i == 0 else ""}>{e(lab)}'
                   f'<span>{len(ms)}</span></button>' for i, (lab, ms) in enumerate(days))
    panes = []
    for i, (lab, ms) in enumerate(days):
        cards = []
        for m in ms:
            body, grp = "", None
            for g, bet, odds, sites, edge in m["bets"]:
                if g != grp:
                    body += f"<tr class=grp><td colspan=3>{'Match result' if g == 'Result' else 'Total goals'}</td></tr>"
                    grp = g
                body += _row(bet, odds, sites, edge)
            cards.append(f"""<div class=mcard><h3>{e(m['home'])} v {e(m['away'])}</h3>
<div class=meta>{e(m['league'])} · {m['ko'].strftime('%a %b %-d, %-I:%M %p')} ET</div>
<div class=tw><table><tr><th>Bet</th><th class=n>Best odds</th><th class=n>Expected per $100</th></tr>{body}</table></div></div>""")
        panes.append(f'<div class=daypane data-day="{i}"{" hidden" if i else ""}><h3 class=dayhead>{e(lab)}</h3>'
                     f'<div class=mlist>{"".join(cards)}</div></div>')
    js = ("<script>document.querySelectorAll('.daytab').forEach(t=>t.addEventListener('click',()=>{"
          "document.querySelectorAll('.daytab').forEach(x=>x.removeAttribute('aria-selected'));t.setAttribute('aria-selected','true');"
          "document.querySelectorAll('.daypane').forEach(p=>p.hidden=p.dataset.day!==t.dataset.day)}));"
          "document.documentElement.classList.add('js')</script>")
    content = (f'<div class=daytabs role=tablist>{tabs}</div>{"".join(panes)}{js}' if days else
               "<div class=empty>No upcoming matches in the latest odds.</div>")
    return f"""<!doctype html><html lang=en><head>{theme.HEAD}
{theme.meta("best-prices.html", "Best prices by match · Today's Soccer Bets", "Where to place each soccer bet: the best odds for every match result and goals line, across US sportsbooks and prediction markets.")}
<meta name=description content="The best odds and the site offering them for every bet on every upcoming match.">
<style>{CSS}{PAGE_CSS}</style></head><body>
{theme.nav("prices")}
<section class=hero><div class=wrap>
<p class=eyebrow>Best prices</p>
<h1>Where to place each bet.</h1>
<p class=lede>For every upcoming match: the best odds for each bet, the site offering them, and the expected result per $100 at that price.</p>
<p class=updated>Last updated {stamp}</p>
</div></section>
<section class=section style="padding-top:0"><div class=wrap>
<p class=sub>{len(M)} matches. Match results compared across {len(set(quotes['site'])) if len(quotes) else 0} sites; total goals across US sportsbooks, for today's matches only. Green means the price pays more than the bet's chance deserves.</p>
{content}
</div></section>
{theme.footer()}
</body></html>"""
