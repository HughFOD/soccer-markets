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
from .extras import MARKETS
from .usbooks import SITES, american

PAGE_CSS = """
.mlist{display:grid;gap:14px;grid-template-columns:minmax(0,1fr)}
.mcard{background:var(--bg2);border-radius:var(--r);padding:18px 22px 10px}
.mcard h3{font-size:19px;margin:0}.mcard .meta{font-size:13px;color:var(--muted);margin:2px 0 10px}
.mcard table{font-size:15px;table-layout:fixed;width:100%}.mcard td{overflow-wrap:anywhere}.mcard th,.mcard td{padding:9px 6px}.mcard td.n{white-space:nowrap}.mcard th.n{white-space:normal}
.mcard .odds{font-weight:700;font-variant-numeric:tabular-nums}
.mcard .site{display:block;color:var(--link);font-weight:500;font-size:13px}
.mcard .pos{color:var(--good);font-weight:700}.mcard .neg{color:var(--muted)}
.mcard .grp td{color:var(--muted);font-size:12px;font-weight:600;padding-top:14px;border-bottom:0;text-transform:uppercase;letter-spacing:.04em}
.mcard tr.bet{cursor:pointer}.mcard tr.bet td:first-child::after{content:"›";display:inline-block;margin-left:6px;color:var(--muted);font-weight:600;transition:transform .15s}
.mcard tr.bet.open td:first-child::after{transform:rotate(90deg)}.mcard tr.bet:hover td{background:var(--hair)}
.mcard tr.all td{padding:0 6px 10px;border-bottom:1px solid var(--hair);max-width:0}
.allsites{display:grid;grid-template-columns:1fr auto auto;gap:4px 14px;font-size:13px;background:var(--tile);border-radius:var(--r);padding:10px 12px}
.allsites b{font-weight:600}.allsites .n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.finder{display:flex;gap:8px;margin:0 0 10px}
.finder input[type=search]{flex:1;min-width:0;font:inherit;font-size:16px;padding:10px 16px;border-radius:var(--r);border:1px solid var(--line);background:var(--bg);color:var(--ink)}
.finder button{flex:none;font:inherit;font-size:15px;border:1px solid var(--line);border-radius:var(--r);padding:8px 16px;background:var(--bg);color:var(--ink);cursor:pointer}
.finder button[aria-expanded=true]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.filters{display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;background:var(--bg2);border-radius:var(--r);padding:12px 14px;margin:0 0 10px;font-size:15px}
.filters select{font:inherit;font-size:15px;padding:6px 10px;border-radius:var(--r);border:1px solid var(--line);background:var(--bg);color:var(--ink)}
.filters label{display:flex;gap:6px;align-items:center;cursor:pointer}
.filters[hidden]{display:none}.hint{font-size:13px;color:var(--muted);margin:0 0 16px}.nomatch{display:none}
.more{margin:6px 0 8px}.more>summary,.mgrp>summary{cursor:pointer;list-style:none;font-weight:600;font-size:15px;padding:10px 6px;color:var(--link)}
.more>summary::-webkit-details-marker,.mgrp>summary::-webkit-details-marker{display:none}
.more>summary::after,.mgrp>summary::after{content:" ›";display:inline-block;transition:transform .15s}
.more[open]>summary::after,.mgrp[open]>summary::after{transform:rotate(90deg)}
.more>summary span,.mgrp>summary span{color:var(--muted);font-weight:400;font-size:13px;margin-left:4px}
.mgrp{border-top:1px solid var(--hair)}.mgrp>summary{color:var(--ink);font-size:14px}
.tw[hidden]{display:none}.search .dayhead{display:block;margin:22px 0 10px}.search .daypane[hidden]{display:none}.empty[hidden]{display:none}
html:not(.js) .finder,html:not(.js) .filters,html:not(.js) .hint{display:none}
@media (max-width:520px){.mcard{padding:16px 14px 8px}.mcard table{font-size:14px}.mcard th,.mcard td{padding:8px 4px}}
"""


# Order of matches within each day: these competitions first, in this order, then the rest by kick-off time.
LEAGUE_ORDER = {name: i for i, name in enumerate(
    ["Champions League", "Premier League", "La Liga", "Ligue 1", "Bundesliga", "Serie A"])}


def _usd(x: float) -> str:
    if x is None or not np.isfinite(x):
        return "—"
    v = 100 * x
    return f"−${-v:.2f}" if v < -0.005 else f"+${v:.2f}"


def _odds(o: float) -> str:
    return american(o).replace("-", "−")


def _row(kind: str, bet: str, odds: float, sites: list[str], edge: float, every: list[tuple]) -> str:
    """One bet: best odds, the sites offering them and the expected result; tapping it shows every site."""
    e = html.escape
    good = bool(np.isfinite(edge) and edge > 0)
    cls = "pos" if good else "neg"
    allr = "".join(f"<b>{e(SITES[s][0])}</b><span class=n>{_odds(o)}</span>"
                   f"<span class='n {'pos' if np.isfinite(g) and g > 0 else 'neg'}'>{_usd(g)}</span>" for s, o, g in every)
    return (f"<tr class=bet data-kind=\"{e(kind)}\" data-pos={int(good)} data-t=\"{e(bet.lower())}\" tabindex=0 aria-expanded=false><td>{e(bet)}</td>"
            f"<td class=n><span class=odds>{_odds(odds)}</span><span class=site>{e(' / '.join(sites))}</span></td>"
            f"<td class='n {cls}'>{_usd(edge)}</td></tr>"
            f"<tr class=all hidden><td colspan=3><div class=allsites>{allr}</div></td></tr>")


def matches_by_day(M: pd.DataFrame, quotes: pd.DataFrame, totals: pd.DataFrame | None,
                   now: pd.Timestamp | None = None, extras: pd.DataFrame | None = None,
                   ranked: bool = False) -> list[tuple[str, list[dict]]]:
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
        more = {}
        if extras is not None and len(extras):
            x = extras[extras["id"] == r["id"]]
            mo = {k: i for i, k in enumerate(MARKETS)}
            x = x.assign(_m=x["market"].map(mo), _p=x["point"].abs(),
                         _o=x["outcome"].map({"Over": 0, "Under": 1, "Yes": 0, "No": 1}).fillna(2)
                         ).sort_values(["_m", "who", "_p", "point", "_o", "outcome"])
            for (mk, line, outc), g in x.groupby(["market", "line", "outcome"], sort=False):
                b = g[g["best"]].sort_values("site", key=lambda c: c.map(order))
                more.setdefault(g["group"].iloc[0], []).append(
                    (g["group"].iloc[0], g["label"].iloc[0], float(b["odds"].iloc[0]), [SITES[s][0] for s in b["site"]],
                     float(b["edge"].max()) if b["edge"].notna().any() else float("nan"), every(g)))
        out.setdefault(ko.date(), []).append({"ko": ko, "home": r["home"], "away": r["away"], "league": r["league"],
                                              "bets": bets, "more": more})
    today = now.date()
    res = []
    for day in sorted(out):
        label = "Today" if day == today else "Tomorrow" if (day - today).days == 1 else pd.Timestamp(day).strftime("%a %b %-d")
        res.append((label, sorted(out[day], key=lambda m: (LEAGUE_ORDER.get(m["league"], len(LEAGUE_ORDER)) if ranked else 0, m["ko"]))))
    return res


def build(M: pd.DataFrame, quotes: pd.DataFrame, totals: pd.DataFrame | None, stamp: str,
          extras: pd.DataFrame | None = None, search: bool = False) -> str:
    """The Prices page, or with search=True the Search page: the same matches, found by search and filters."""
    from .extras import GROUPS
    e = html.escape
    days = matches_by_day(M, quotes, totals, extras=extras, ranked=not search)
    cols = '<colgroup><col><col style="width:30%"><col style="width:26%"></colgroup>'
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
            more = ""
            if m["more"]:
                n = sum(len(v) for v in m["more"].values())
                parts = "".join(
                    f'<details class=mgrp><summary>{e(gname)} <span>{len(m["more"][gname])}</span></summary>'
                    f'<div class=tw><table>{cols}{"".join(_row(*b) for b in m["more"][gname])}</table></div></details>'
                    for gname in GROUPS if gname in m["more"])
                more = f'<details class=more><summary>More bets <span>{n}</span></summary>{parts}</details>'
            cards.append(f"""<div class=mcard data-ko="{m['ko'].tz_convert('UTC').isoformat()}" data-find="{find}" data-league="{e(m['league'])}"><h3>{e(m['home'])} v {e(m['away'])}</h3>
<div class=meta>{e(m['league'])} · {m['ko'].strftime('%a %b %-d, %-I:%M %p')} ET</div>
<div class=tw><table>{cols}<tr><th>Bet</th><th class=n>Best odds</th><th class=n>Expected per $100</th></tr>{body}</table></div>{more}</div>""")
        d = ms[0]["ko"].date()
        panes.append(f'<div class=daypane data-day="{i}" data-date="{d.isoformat()}" data-label="{pd.Timestamp(d).strftime("%a %b %-d")}"'
                     f'{" hidden" if i and not search else ""}><h3 class=dayhead>{e(lab)}</h3>'
                     f'<div class=mlist>{"".join(cards)}</div><div class="empty nomatch">No matches fit your search on this day.</div></div>')
    leagues = sorted({m["league"] for _, ms in days for m in ms})
    finder = (f'<div class=finder><input type=search id=q placeholder="Search a team or league" aria-label="Search a team or league"></div>'
              f'<div class=filters id=filters><select id=lg aria-label=League><option value="">All leagues</option>'
              + "".join(f"<option>{e(l)}</option>" for l in leagues) +
              '</select><select id=kind aria-label="Bet type"><option value="">All bets</option><option value=Result>Match result</option>'
              '<option value=Goals>Goals</option>' + "".join(f'<option>{g}</option>' for g in GROUPS[2:]) + '</select>'
              '<label><input type=checkbox id=pos> Only green bets</label></div>'
              '<p class="empty prompt">Type a team or league, or pick a filter.</p>'
              '<p class="empty none" hidden>Nothing matches. Try another name or filter.</p>')
    bar = finder.split('<p class="empty prompt">')[0]     # the Prices page: same search and filters, no prompt
    hint = '<p class=hint>Tap any bet to compare every site\'s odds.</p>'
    rows_js = """document.addEventListener('click',function(ev){var r=ev.target.closest('tr.bet');if(!r)return;var o=r.classList.toggle('open');
 r.setAttribute('aria-expanded',o);r.nextElementSibling.hidden=!o});
document.addEventListener('keydown',function(ev){if((ev.key==='Enter'||ev.key===' ')&&ev.target.matches('tr.bet')){ev.preventDefault();ev.target.click()}});
document.documentElement.classList.add('js');"""
    tabs_js = """<script>(function(){document.querySelectorAll('.daytab').forEach(function(t){t.addEventListener('click',function(){
document.querySelectorAll('.daytab').forEach(function(x){x.removeAttribute('aria-selected')});t.setAttribute('aria-selected','true');
document.querySelectorAll('.daypane').forEach(function(p){p.hidden=p.dataset.day!==t.dataset.day})})});
""" + rows_js + "})();</script>"
    search_js = """<script>(function(){
var panes=[].slice.call(document.querySelectorAll('.daypane')),q=document.getElementById('q'),lg=document.getElementById('lg'),
kind=document.getElementById('kind'),pos=document.getElementById('pos'),prompt=document.querySelector('.prompt'),none=document.querySelector('.none');
function show(){var term=q.value.trim().toLowerCase(),act=!!(term||lg.value||kind.value||pos.checked),total=0;
 panes.forEach(function(p){var n=0;
  p.querySelectorAll('.mcard').forEach(function(c){var cm=!term||c.dataset.find.indexOf(term)>=0,ok=act&&(!lg.value||c.dataset.league===lg.value),rows=0;
   c.querySelectorAll('tr.bet').forEach(function(r){var v=ok&&(cm||r.dataset.t.indexOf(term)>=0)&&(!kind.value||r.dataset.kind===kind.value)&&(!pos.checked||r.dataset.pos==='1');
    r.hidden=!v;if(!v){r.classList.remove('open');r.nextElementSibling.hidden=true}if(v)rows++});
   c.querySelectorAll('tr.grp').forEach(function(g){g.hidden=!!kind.value&&g.dataset.kind!==kind.value||!c.querySelector('tr.bet[data-kind='+g.dataset.kind+']:not([hidden])')});
   var deep=!!(kind.value||pos.checked||(term&&!cm));
   c.querySelectorAll('details').forEach(function(d){var has=!!d.querySelector('tr.bet:not([hidden])');d.hidden=!has;
    if(deep){if(has&&!d.open){d.open=true;d.dataset.auto=1}}else if(d.dataset.auto){d.open=false;delete d.dataset.auto}});
   var mt=c.querySelector(':scope>.tw');if(mt)mt.hidden=!mt.querySelector('tr.bet:not([hidden])');
   c.hidden=!rows;if(rows)n++});
  p.hidden=!n;total+=n});
 prompt.hidden=act;none.hidden=!act||total>0}
[q,lg,kind,pos].forEach(function(el){el.addEventListener('input',show);el.addEventListener('change',show)});
""" + rows_js + "show();})();</script>"
    prices_js = """<script>(function(){
var q=document.getElementById('q'),lg=document.getElementById('lg'),kind=document.getElementById('kind'),pos=document.getElementById('pos');
function show(){var term=q.value.trim().toLowerCase(),act=!!(term||lg.value||kind.value||pos.checked),counts={};
 document.querySelectorAll('.daypane').forEach(function(p){var n=0;
  p.querySelectorAll('.mcard').forEach(function(c){var cm=!term||c.dataset.find.indexOf(term)>=0,ok=!lg.value||c.dataset.league===lg.value,rows=0;
   c.querySelectorAll('tr.bet').forEach(function(r){var v=ok&&(cm||r.dataset.t.indexOf(term)>=0)&&(!kind.value||r.dataset.kind===kind.value)&&(!pos.checked||r.dataset.pos==='1');
    r.hidden=!v;if(!v){r.classList.remove('open');r.nextElementSibling.hidden=true}if(v)rows++});
   c.querySelectorAll('tr.grp').forEach(function(g){g.hidden=!!kind.value&&g.dataset.kind!==kind.value||!c.querySelector('tr.bet[data-kind='+g.dataset.kind+']:not([hidden])')});
   var deep=!!(kind.value||pos.checked||(term&&!cm));
   c.querySelectorAll('details').forEach(function(d){var has=!!d.querySelector('tr.bet:not([hidden])');d.hidden=!has;
    if(deep){if(has&&!d.open){d.open=true;d.dataset.auto=1}}else if(d.dataset.auto){d.open=false;delete d.dataset.auto}});
   var mt=c.querySelector(':scope>.tw');if(mt)mt.hidden=!mt.querySelector('tr.bet:not([hidden])');
   c.hidden=!rows;if(rows)n++});
  var nm=p.querySelector('.nomatch');if(nm)nm.style.display=act&&!n?'block':'none';
  var t=document.querySelector('.daytab[data-day="'+p.dataset.day+'"]'),sp=t&&t.querySelector('span');
  if(sp){if(!sp.dataset.all)sp.dataset.all=sp.textContent;sp.textContent=act?n:sp.dataset.all}
  counts[p.dataset.day]=n});
 if(act){var cur=document.querySelector('.daypane:not([hidden])');if(cur&&!counts[cur.dataset.day]){
  for(var d in counts){if(counts[d]){var t2=document.querySelector('.daytab[data-day="'+d+'"]');if(t2)t2.click();break}}}}}
[q,lg,kind,pos].forEach(function(el){el.addEventListener('input',show);el.addEventListener('change',show)});show()})();</script>"""
    if not days:
        content = "<div class=empty>No upcoming matches in the latest odds.</div>"
    elif search:
        content = f'{finder}{hint}<div class=results>{"".join(panes)}</div>{theme.FRESH_JS}{search_js}'
    else:
        content = f'{bar}{hint}<div class=daytabs role=tablist>{tabs}</div>{"".join(panes)}{theme.FRESH_JS}{tabs_js}{prices_js}'
    if search:
        head = (theme.meta("search.html", "Search every bet · Today's Soccer Bets",
                           "Find any team or league and compare every site's odds on every soccer bet."), "search",
                "Search", "Search every bet.", "Find any team or league and compare every site's odds.")
    else:
        head = (theme.meta("best-prices.html", "Compare the Best Betting Odds Across Sportsbooks for Every Upcoming Match | Today's Soccer Bets",
                           "Where to place each soccer bet: the best odds for every match result and goals line, across US sportsbooks and prediction markets."),
                "prices", "Best prices", "Compare the Best Betting Odds Across Sportsbooks for Every Upcoming Match.",
                "Which site pays the most for each bet, and what you can expect to win or lose per $100.")
    return f"""<!doctype html><html lang=en><head>{theme.HEAD}
{head[0]}
<style>{CSS}{PAGE_CSS}</style></head><body{" class=search" if search else ""}>
{theme.nav(head[1])}
<section class=hero><div class=wrap>
<p class=eyebrow>{head[2]}</p>
<h1>{head[3]}</h1>
<p class=lede>{head[4]}</p>
<p class=updated>Last updated {stamp}</p>
</div></section>
<section class=section style="padding-top:0"><div class=wrap>
<p class=sub>Green marks a good bet: the odds pay more than its chance of winning deserves.</p>
{content}
</div></section>
{theme.footer()}
</body></html>"""
