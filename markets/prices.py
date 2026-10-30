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
.mcard table{font-size:15px;table-layout:fixed;width:100%}.mcard th:nth-child(2){width:30%}.mcard th:nth-child(3){width:26%}.mcard td{overflow-wrap:anywhere}.mcard th,.mcard td{padding:9px 6px}.mcard td.n{white-space:nowrap}.mcard th.n{white-space:normal}
.mcard .odds{font-weight:700;font-variant-numeric:tabular-nums}
.mcard .site{display:block;color:var(--link);font-weight:500;font-size:13px}
.mcard .pos{color:var(--good);font-weight:700}.mcard .neg{color:var(--muted)}
.mcard .grp td{color:var(--muted);font-size:12px;font-weight:600;padding-top:14px;border-bottom:0;text-transform:uppercase;letter-spacing:.04em}
.mcard tr.bet{cursor:pointer}.mcard tr.bet td:first-child::after{content:"›";display:inline-block;margin-left:6px;color:var(--muted);font-weight:600;transition:transform .15s}
.mcard tr.bet.open td:first-child::after{transform:rotate(90deg)}.mcard tr.bet:hover td{background:var(--hair)}
.mcard tr.all td{padding:0 6px 10px;border-bottom:1px solid var(--hair);max-width:0}
.allsites{display:grid;grid-template-columns:1fr auto auto;gap:4px 14px;font-size:13px;background:var(--tile);border-radius:12px;padding:10px 12px}
.allsites b{font-weight:600}.allsites .n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.finder{display:flex;gap:8px;margin:0 0 10px}
.finder input[type=search]{flex:1;min-width:0;font:inherit;font-size:16px;padding:10px 16px;border-radius:980px;border:1px solid var(--line);background:var(--bg);color:var(--ink)}
.finder button{flex:none;font:inherit;font-size:15px;border:1px solid var(--line);border-radius:980px;padding:8px 16px;background:var(--bg);color:var(--ink);cursor:pointer}
.finder button[aria-expanded=true]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.filters{display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;background:var(--bg2);border-radius:14px;padding:12px 14px;margin:0 0 10px;font-size:15px}
.filters select{font:inherit;font-size:15px;padding:6px 10px;border-radius:10px;border:1px solid var(--line);background:var(--bg);color:var(--ink)}
.filters label{display:flex;gap:6px;align-items:center;cursor:pointer}
.filters[hidden]{display:none}.hint{font-size:13px;color:var(--muted);margin:0 0 16px}.nomatch{display:none}
html:not(.js) .finder,html:not(.js) .filters,html:not(.js) .hint{display:none}
@media (max-width:520px){.mcard{padding:16px 14px 8px}.mcard table{font-size:14px}.mcard th,.mcard td{padding:8px 4px}}
"""


def _usd(x: float) -> str:
    v = 100 * x
    return f"−${-v:.2f}" if v < -0.005 else f"+${v:.2f}"


def _odds(o: float) -> str:
    return american(o).replace("-", "−")


def _row(kind: str, bet: str, odds: float, sites: list[str], edge: float, every: list[tuple]) -> str:
    """One bet: best odds, the sites offering them and the expected result; tapping it shows every site."""
    e = html.escape
    cls = "pos" if edge > 0 else "neg"
    allr = "".join(f"<b>{e(SITES[s][0])}</b><span class=n>{_odds(o)}</span><span class='n {'pos' if g > 0 else 'neg'}'>{_usd(g)}</span>"
                   for s, o, g in every)
    return (f"<tr class=bet data-kind={kind} data-pos={int(edge > 0)} tabindex=0 aria-expanded=false><td>{e(bet)}</td>"
            f"<td class=n><span class=odds>{_odds(odds)}</span><span class=site>{e(' / '.join(sites))}</span></td>"
            f"<td class='n {cls}'>{_usd(edge)}</td></tr>"
            f"<tr class=all hidden><td colspan=3><div class=allsites>{allr}</div></td></tr>")


def matches_by_day(M: pd.DataFrame, quotes: pd.DataFrame, totals: pd.DataFrame | None,
                   now: pd.Timestamp | None = None) -> list[tuple[str, list[dict]]]:
    """[(day label, [match, ...])]; each match has its bets with the best odds and sites."""
    if not len(M):
        return []
    now = now or pd.Timestamp.now(tz=ET)
    order = {k: i for i, k in enumerate(SITES)}
    best = quotes[quotes["best"]] if len(quotes) else quotes
    tbest = totals[totals["best"]] if totals is not None and len(totals) else None

    def every(g):  # every site's price for one bet, best first
        g = g.assign(_o=g["site"].map(order)).sort_values(["odds", "_o"], ascending=[False, True])
        return [(s, float(o), float(d)) for s, o, d in zip(g["site"], g["odds"], g["edge"])]
    out: dict = {}
    for _, r in M.iterrows():
        ko = pd.Timestamp(r["kickoff"]).tz_convert(ET)
        if ko <= now:
            continue
        bets = []
        for o, name in (("h", f"{r['home']} to win"), ("d", "Draw"), ("a", f"{r['away']} to win")):
            g = best[(best["id"] == r["id"]) & (best["result"] == o)].sort_values("site", key=lambda c: c.map(order))
            if len(g):
                allq = quotes[(quotes["id"] == r["id"]) & (quotes["result"] == o)]
                bets.append(("Result", name, float(g["odds"].iloc[0]), [SITES[s][0] for s in g["site"]], float(g["edge"].iloc[0]),
                             every(allq)))
        if tbest is not None:
            g2 = tbest[tbest["id"] == r["id"]]
            for (point, side), g in sorted(g2.groupby(["point", "side"]), key=lambda kv: (kv[0][0], kv[0][1] != "Over")):
                g = g.sort_values("site", key=lambda c: c.map(order))
                allq = totals[(totals["id"] == r["id"]) & (totals["point"] == point) & (totals["side"] == side)]
                bets.append(("Goals", f"{side} {point:g} goals", float(g["odds"].iloc[0]),
                             [SITES[s][0] for s in g["site"]], float(g["edge"].iloc[0]), every(allq)))
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
            for g, bet, odds, sites, edge, allp in m["bets"]:
                if g != grp:
                    body += f"<tr class=grp data-kind={g}><td colspan=3>{'Match result' if g == 'Result' else 'Total goals'}</td></tr>"
                    grp = g
                body += _row(g, bet, odds, sites, edge, allp)
            find = e(f"{m['home']} {m['away']} {m['league']}".lower())
            cards.append(f"""<div class=mcard data-find="{find}" data-league="{e(m['league'])}"><h3>{e(m['home'])} v {e(m['away'])}</h3>
<div class=meta>{e(m['league'])} · {m['ko'].strftime('%a %b %-d, %-I:%M %p')} ET</div>
<div class=tw><table><tr><th>Bet</th><th class=n>Best odds</th><th class=n>Expected per $100</th></tr>{body}</table></div></div>""")
        panes.append(f'<div class=daypane data-day="{i}"{" hidden" if i else ""}><h3 class=dayhead>{e(lab)}</h3>'
                     f'<div class=mlist>{"".join(cards)}</div><div class="empty nomatch">No matches fit your search on this day.</div></div>')
    leagues = sorted({m["league"] for _, ms in days for m in ms})
    finder = (f'<div class=finder><input type=search id=q placeholder="Search a team or league" aria-label="Search a team or league">'
              f'<button type=button id=fbtn aria-expanded=false aria-controls=filters>Filters</button></div>'
              f'<div class=filters id=filters hidden><select id=lg aria-label=League><option value="">All leagues</option>'
              + "".join(f"<option>{e(l)}</option>" for l in leagues) +
              '</select><select id=kind aria-label="Bet type"><option value="">All bets</option><option value=Result>Match result</option>'
              '<option value=Goals>Total goals</option></select>'
              '<label><input type=checkbox id=pos> Only green bets</label></div>'
              '<p class=hint>Tap any bet to compare every site\'s odds.</p>')
    js = """<script>(function(){
var tabs=[].slice.call(document.querySelectorAll('.daytab')),panes=[].slice.call(document.querySelectorAll('.daypane')),
q=document.getElementById('q'),lg=document.getElementById('lg'),kind=document.getElementById('kind'),pos=document.getElementById('pos'),
fb=document.getElementById('fbtn'),fp=document.getElementById('filters'),day='0';
function show(){var term=q.value.trim().toLowerCase();
 panes.forEach(function(p,i){var n=0;
  p.querySelectorAll('.mcard').forEach(function(c){var ok=(!term||c.dataset.find.indexOf(term)>=0)&&(!lg.value||c.dataset.league===lg.value),rows=0;
   c.querySelectorAll('tr.bet').forEach(function(r){var v=ok&&(!kind.value||r.dataset.kind===kind.value)&&(!pos.checked||r.dataset.pos==='1');
    r.hidden=!v;if(!v){r.classList.remove('open');r.nextElementSibling.hidden=true}if(v)rows++});
   c.querySelectorAll('tr.grp').forEach(function(g){g.hidden=!!kind.value&&g.dataset.kind!==kind.value||!c.querySelector('tr.bet[data-kind='+g.dataset.kind+']:not([hidden])')});
   c.hidden=!rows;if(rows)n++});
  tabs[i].querySelector('span').textContent=n;p.querySelector('.nomatch').style.display=n?'none':'block';
  p.hidden=p.dataset.day!==day});}
tabs.forEach(function(t){t.addEventListener('click',function(){tabs.forEach(function(x){x.removeAttribute('aria-selected')});
 t.setAttribute('aria-selected','true');day=t.dataset.day;show()})});
[q,lg,kind,pos].forEach(function(el){el.addEventListener('input',show);el.addEventListener('change',show)});
q.addEventListener('input',function(){if(!q.value.trim())return;var cur=panes[+day];if(cur&&cur.querySelector('.mcard:not([hidden])'))return;
 for(var i=0;i<panes.length;i++){if(panes[i].querySelector('.mcard:not([hidden])')){tabs[i].click();break}}});
fb.addEventListener('click',function(){var o=fp.hidden;fp.hidden=!o;fb.setAttribute('aria-expanded',o)});
document.addEventListener('click',function(ev){var r=ev.target.closest('tr.bet');if(!r)return;var o=r.classList.toggle('open');
 r.setAttribute('aria-expanded',o);r.nextElementSibling.hidden=!o});
document.addEventListener('keydown',function(ev){if((ev.key==='Enter'||ev.key===' ')&&ev.target.matches('tr.bet')){ev.preventDefault();ev.target.click()}});
document.documentElement.classList.add('js');})();</script>"""
    content = (f'{finder}<div class=daytabs role=tablist>{tabs}</div>{"".join(panes)}{js}' if days else
               "<div class=empty>No upcoming matches in the latest odds.</div>")
    return f"""<!doctype html><html lang=en><head>{theme.HEAD}
{theme.meta("best-prices.html", "Compare the Best Betting Odds Across Sportsbooks for Every Upcoming Match | Today's Soccer Bets", "Where to place each soccer bet: the best odds for every match result and goals line, across US sportsbooks and prediction markets.")}
<style>{CSS}{PAGE_CSS}</style></head><body>
{theme.nav("prices")}
<section class=hero><div class=wrap>
<p class=eyebrow>Best prices</p>
<h1>Compare the Best Betting Odds Across Sportsbooks for Every Upcoming Match.</h1>
<p class=lede>Which site pays the most for each bet, and what you can expect to win or lose per $100.</p>
<p class=updated>Last updated {stamp}</p>
</div></section>
<section class=section style="padding-top:0"><div class=wrap>
<p class=sub>{len(M)} matches. Match results compared across {len(set(quotes['site'])) if len(quotes) else 0} sites; total goals for today's matches in the two busiest leagues. Green means the price pays more than the bet's chance deserves.</p>
{content}
</div></section>
{theme.footer()}
</body></html>"""
