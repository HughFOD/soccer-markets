"""The homepage: this week's soccer odds across US sportsbooks and prediction markets.

Built by markets.weekly from the saved Odds API responses and output/results.json.
"""
from __future__ import annotations

import html
import re
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
.pick{background:var(--bg2);border-radius:var(--r);padding:22px 22px 20px;display:flex;flex-direction:column;gap:4px}
.pick .meta{font-size:13px;color:var(--muted)}
.pick .m{font-size:19px;font-weight:600;line-height:1.25;letter-spacing:-.015em}
.pick .bet{margin-top:10px;font-size:15px;color:var(--ink2)}
.pick .bet b{display:block;font:700 26px/1.15 var(--sans);color:var(--ink);letter-spacing:-.02em;margin:2px 0}
.pick .vs{font-size:14px;color:var(--muted)}
.edge{display:inline-block;background:var(--goodbg);color:var(--good);font-size:13px;font-weight:600;padding:3px 10px;border-radius:var(--r);margin-left:6px;vertical-align:middle}
.tally{font-size:19px;margin:26px 0 8px}.how{counter-reset:s;list-style:none;padding:0;margin:0 0 6px;display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.how li{counter-increment:s;background:var(--bg2);border-radius:var(--r);padding:14px 16px 14px 48px;position:relative;font-size:15px;color:var(--ink2);line-height:1.4}
.how li::before{content:counter(s);position:absolute;left:14px;top:13px;width:24px;height:24px;border-radius:50%;background:var(--accent);color:#fff;font-size:13px;font-weight:700;display:grid;place-items:center}
.how b{color:var(--ink);display:block;margin-bottom:2px}
@media (max-width:820px){.how{grid-template-columns:1fr}}
.bigstat{display:flex;gap:18px;align-items:center;background:var(--tile);border-radius:var(--r);padding:22px 24px;margin:18px 0}
.bigstat .v{font:600 44px/1 var(--mono);letter-spacing:-.03em;color:var(--good)}
.bigstat .l{color:var(--ink2);font-size:16px}.csub{color:var(--muted);font-size:14px;margin:0 0 12px}
.hbars{display:grid;gap:10px;margin-bottom:16px}.hb{display:grid;grid-template-columns:78px 1fr 44px 80px;gap:12px;align-items:center;font-size:14px}
.hl{color:var(--ink2)}.hv{font-weight:700;text-align:right;font-variant-numeric:tabular-nums}.hn{color:var(--muted);font-size:12px;text-align:right}
.ht{position:relative;height:14px;background:var(--hair);border-radius:7px}.hf{position:absolute;inset:0 auto 0 0;background:var(--accent);border-radius:7px}
.h50{position:absolute;left:50%;top:-4px;bottom:-4px;width:2px;background:var(--ink2);opacity:.5}
.nums summary{cursor:pointer;color:var(--link);font-weight:500;margin:6px 0 10px}
@media (max-width:520px){.bigstat{flex-direction:column;align-items:flex-start}.hb{grid-template-columns:70px 1fr 40px}.hn{display:none}}
.why{grid-column:2/-1;margin-top:-6px;font-size:14px;min-width:0}.bet-main{min-width:0}.why summary{cursor:pointer;color:var(--link);font-weight:500;list-style:none}
.why summary::-webkit-details-marker{display:none}.why summary::after{content:" ›";display:inline-block;transition:transform .15s}
.why[open] summary::after{transform:rotate(90deg)}.why p{margin:8px 0;color:var(--ink2);line-height:1.45}
.whygrid{display:grid;grid-template-columns:1fr auto auto;gap:3px 14px;font-size:13px;background:var(--bg2);border-radius:var(--r);padding:8px 12px}
.whygrid .n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.empty{background:var(--bg2);border-radius:var(--r);padding:22px;color:var(--muted)}
.daytabs{display:flex;gap:8px;overflow-x:auto;padding:2px 0 18px;scrollbar-width:none}.daytabs::-webkit-scrollbar{display:none}
.daytab{flex:none;font:inherit;font-size:15px;border:0;border-radius:var(--r);padding:8px 16px;background:var(--bg2);color:var(--ink);cursor:pointer;letter-spacing:-.01em}
.daytab span{margin-left:7px;color:var(--muted);font-size:13px}
.daytab[aria-selected=true]{background:var(--ink);color:var(--bg)}.daytab[aria-selected=true] span{color:inherit;opacity:.7}
html:not(.js) .daytabs{display:none}html:not(.js) .daypane{display:block!important;margin-bottom:28px}
.dayhead{display:none}html:not(.js) .dayhead{display:block}
.bets{list-style:none;margin:0;padding:0;background:var(--bg2);border-radius:var(--r);overflow:hidden}
.bet-row{display:grid;grid-template-columns:44px 1fr auto auto;gap:18px;align-items:center;padding:16px 22px;border-top:1px solid var(--hair)}
.bet-row:first-child{border-top:0}
.rank{font:600 18px var(--mono);color:var(--muted);text-align:center}
.bet-row:first-child .rank{color:var(--blue)}
.bet-what{font-size:19px;font-weight:600;letter-spacing:-.015em;line-height:1.25}
.bet-match{font-size:14px;color:var(--muted);margin-top:2px}
.bet-why{font-size:14px;color:var(--ink2);margin-top:6px}.bet-why b{font-weight:600;color:var(--ink)}
.bet-where{text-align:right}.bet-odds{font:600 22px/1.1 var(--mono);letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.bet-site{font-size:14px;color:var(--link);font-weight:500}
.bet-value{text-align:right;min-width:116px}.bet-value .edge{margin:0}.bet-chance{font-size:13px;color:var(--muted);margin-top:4px}
.few{font-size:14px;color:var(--muted);margin:12px 4px 0}
@media (max-width:640px){.bet-row{grid-template-columns:30px 1fr auto;gap:4px 12px;padding:14px 16px}
  .rank{font-size:18px;grid-row:1/3}.bet-where{grid-column:3;grid-row:1}.bet-value{grid-column:2/4;grid-row:2;text-align:left;min-width:0;display:flex;gap:10px;align-items:center}
  .bet-main{grid-column:2;grid-row:1}.why{grid-column:2/4;grid-row:3;margin-top:4px}.bet-chance{margin:0}.bet-what{font-size:17px}.bet-odds{font-size:20px}}
.bar{display:inline-block;height:6px;border-radius:3px;background:var(--blue);vertical-align:middle;margin-right:8px}
.kind{font-size:12px;color:var(--muted)}
details.league{background:var(--tile);border-radius:var(--r);margin:12px 0;overflow:hidden}
details.league>summary{cursor:pointer;padding:18px 56px 18px 22px;font-size:19px;font-weight:600;list-style:none;position:relative;letter-spacing:-.015em}
details.league>summary::-webkit-details-marker{display:none}
details.league>summary:after{content:"+";position:absolute;right:22px;top:50%;transform:translateY(-52%);font-weight:300;font-size:26px;color:var(--muted);line-height:1}
details.league[open]>summary:after{content:"−"}
details.league>summary span{color:var(--muted);font-weight:400;font-size:15px;margin-left:8px}
.match{padding:6px 22px 18px}
.match h4{margin:10px 0 8px;font-size:16px;font-weight:600}.match h4 small{color:var(--muted);font-weight:400;font-size:13px}
.match .tablewrap{background:var(--bg2);border-radius:var(--r)}
.match th,.match td{padding:9px 12px}
.best{color:var(--good);font-weight:700}
.match table tr td.good{background:var(--goodbg)}
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
                totals: pd.DataFrame | None = None, extras: pd.DataFrame | None = None,
                everything: bool = False):
    """[(day label, [bet, ...])] for each day from today on, highest expected return first.

    A bet is one result of one match at its best price across the sites. Its expected chance is the
    consensus of all the sites with their cuts removed; its expected return is expected chance x decimal
    odds - 1. Only bets with a positive expected return are kept. Matches that have kicked off are left out.
    `totals` (from usbooks.price_totals) adds goals over/under bets, priced the same way, and `extras`
    (from extras.price) adds corners, cards, player and other bets that have an expected chance.
    everything=True returns one flat list of every best-price bet, whatever its expected return
    (used by the track record to re-check earlier picks).
    """
    keep = (lambda edge, n: True) if everything else (lambda edge, n: MIN_EDGE < edge <= MAX_EDGE)
    has_totals = totals is not None and len(totals)
    if not len(M) or (not len(quotes) and not has_totals):
        return []
    now = now or pd.Timestamp.now(tz=ET)
    order = {k: i for i, k in enumerate(SITES)}
    # how many sites price each bet
    nsites_result = M.set_index("id")["n_sites"].to_dict() if "n_sites" in M else {}
    nsites_totals = (totals.groupby(["id", "point"])["site"].nunique().to_dict()
                     if totals is not None and len(totals) else {})
    nsites_extra = (extras[extras["edge"].notna()].groupby(["id", "market", "line"])["site"].nunique().to_dict()
                    if extras is not None and len(extras) else {})
    def every_site(df, keys):
        """{bet key: [(site name, decimal odds), ...]} best price first."""
        if df is None or not len(df):
            return {}
        return {k: [(SITES[s][0], float(o)) for s, o in sorted(zip(g["site"], g["odds"]), key=lambda t: (-t[1], order.get(t[0], 99)))]
                for k, g in df.groupby(keys, sort=False)}
    ev_res = every_site(quotes, ["id", "result"]) if len(quotes) else {}
    ev_tot = every_site(totals, ["id", "point", "side"]) if has_totals else {}
    ev_ext = every_site(extras, ["id", "market", "line", "outcome"]) if extras is not None and len(extras) else {}
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
            n = int(nsites_result.get(mid, 0))
            if not keep(edge, n):
                continue
            team = r["home"] if res == "h" else r["away"] if res == "a" else None
            rows.append({"day": r["ko"].date(), "ko": r["ko"], "edge": edge, "odds": american(r["odds"]), "paid": 1 / float(r["odds"]),
                         "bet": f"{team} to win" if team else "Draw", "match": f"{r['home']} v {r['away']}",
                         "league": r["league"], "sites": [SITES[x][0] for x in g["site"]],
                         "chance": float(r[f"cons_{res}"]), "n_sites": n,
                         "id": mid, "dec": float(r["odds"]), "kind": "result", "outcome": res, "point": np.nan,
                         "every": ev_res.get((mid, res), [])})
    if totals is not None and len(totals):
        g2 = totals.copy()
        g2["ko"] = pd.to_datetime(g2["kickoff"]).dt.tz_convert(ET)
        g2 = g2[(g2["ko"] > now) & g2["best"]]
        for (mid, point, side), g in g2.groupby(["id", "point", "side"], sort=False):
            g = g.sort_values("site", key=lambda c: c.map(order))
            r = g.iloc[0]
            edge = float(r["edge"])
            n = int(nsites_totals.get((mid, point), 0))
            if not keep(edge, n):
                continue
            rows.append({"day": r["ko"].date(), "ko": r["ko"], "edge": edge, "odds": american(r["odds"]),
                         "paid": 1 / float(r["odds"]), "bet": f"{side} {point:g} goals",
                         "match": f"{r['home']} v {r['away']}", "league": r["league"],
                         "sites": [SITES[x][0] for x in g["site"]], "chance": float(r["chance"]), "n_sites": n,
                         "id": mid, "dec": float(r["odds"]), "kind": "totals", "outcome": side, "point": float(point),
                         "every": ev_tot.get((mid, point, side), [])})
    if extras is not None and len(extras):
        info = M.set_index("id")[["kickoff", "home", "away", "league"]]
        x = extras[extras["best"] & extras["edge"].notna() & extras["id"].isin(info.index)]
        for (mid, mk, line, outc), g in x.groupby(["id", "market", "line", "outcome"], sort=False):
            g = g.sort_values("site", key=lambda c: c.map(order))
            r = g.iloc[0]
            edge = float(r["edge"])
            ko = pd.Timestamp(info.loc[mid, "kickoff"]).tz_convert(ET)
            n = int(nsites_extra.get((mid, mk, line), 0))
            if ko <= now or not keep(edge, n):
                continue
            rows.append({"day": ko.date(), "ko": ko, "edge": edge, "odds": american(r["odds"]),
                         "paid": 1 / float(r["odds"]), "bet": r["label"],
                         "match": f"{info.loc[mid, 'home']} v {info.loc[mid, 'away']}", "league": info.loc[mid, "league"],
                         "sites": [SITES[s][0] for s in g["site"]], "chance": float(r["chance"]), "n_sites": n,
                         "id": mid, "dec": float(r["odds"]), "kind": mk, "outcome": outc,
                         "point": float(r["point"]) if pd.notna(r["point"]) else np.nan,
                         "every": ev_ext.get((mid, mk, line, outc), [])})
    if everything:
        return rows
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


def why_html(b: dict) -> str:
    """The reasoning behind one pick: what the sites say together, what the best site pays, and the gap."""
    e = html.escape
    fair = american(1 / b["chance"]) if b["chance"] > 0 else ""
    ev = b.get("every") or []
    best = ev[0][1] if ev else b["dec"]
    others = [(s, o) for s, o in ev if o < best - 1e-9]
    nxt = (f" The next best price is {e(others[0][0])} at {american(others[0][1]).replace('-', '−')}." if others else "")
    # "a 79.7% chance" but "an 81.5% chance" / "an 11% chance" (said "eighty", "eleven", "eighteen")
    an = lambda s: "an" if s.startswith("8") or re.match(r"1[18](\D|$)", s) else "a"
    ch, pd_ = f"{100 * b['chance']:.1f}%", f"{100 * b['paid']:.1f}%"
    text = (f"{b['n_sites'] or len(ev)} sites price this bet. With each site's cut removed, together they give it {an(ch)} "
            f"<b>{ch}</b> chance (fair odds {fair.replace('-', '−')}). {e(' and '.join(b['sites']))} "
            f"pay{'s' if len(b['sites']) == 1 else ''} <b>{b['odds'].replace('-', '−')}</b>, as if it had only {an(pd_)} "
            f"<b>{pd_}</b> chance. That gap is worth <b>+${100 * b['edge']:.2f}</b> per $100 on average.{nxt}")
    grid = "".join(f"<span>{e(s)}</span><span class=n>{american(o).replace('-', '−')}</span><span class=n>as if {100 / o:.1f}%</span>"
                   for s, o in ev)
    return (f"<details class=why><summary>Why this bet</summary><p>{text}</p>"
            + (f"<div class=whygrid>{grid}</div>" if grid else "") + "</details>")


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
        items = "".join(f"""<li class=bet-row data-ko="{b['ko'].tz_convert('UTC').isoformat()}"><span class=rank>{k}</span>
<div class=bet-main><div class=bet-what>{e(b['bet'])}</div>
<div class=bet-match>{e(b['match'])} · {e(b['league'])} · {b['ko'].strftime('%-I:%M %p')} ET</div>
<div class=bet-why>Expected to win <b>{chance_pair(b['chance'], b['paid'])[0]}</b> of the time, paid as if <b>{chance_pair(b['chance'], b['paid'])[1]}</b></div></div>
<div class=bet-where><div class=bet-odds>{b['odds'].replace('-', '−')}</div><div class=bet-site>{e(' or '.join(b['sites']))}</div></div>
<div class=bet-value><span class=edge>+${100 * b['edge']:.2f}</span><div class=bet-chance>expected per $100</div></div>
{why_html(b)}</li>"""
                        for k, b in enumerate(bets, 1))
        note = (f"<div class=empty>No bet beats what's expected {when(lab)}. "
                "Every site is charging its full cut, so every bet is expected to lose money.</div>" if not bets else
                "" if len(bets) >= 5 else
                f"<p class=few>Only {len(bets)} bet{'s' if len(bets) != 1 else ''} beat{'s' if len(bets) == 1 else ''} "
                f"what's expected {when(lab)}. The rest are expected to lose money, so they're left out.</p>")
        date = bets[0]["day"] if bets else pd.Timestamp.now(tz=ET).date()
        panes.append(f'<div class=daypane data-day="{i}" data-date="{date.isoformat()}" data-label="{pd.Timestamp(date).strftime("%a %b %-d")}"'
                     f'{" hidden" if i != first else ""}><h3 class=dayhead>{e(lab)}</h3>'
                     + (f'<ol class=bets>{items}</ol>' if bets else '') + f'{note}</div>')
    js = ("<script>document.querySelectorAll('.daytab').forEach(t=>t.addEventListener('click',()=>{"
          "document.querySelectorAll('.daytab').forEach(x=>x.removeAttribute('aria-selected'));t.setAttribute('aria-selected','true');"
          "document.querySelectorAll('.daypane').forEach(p=>p.hidden=p.dataset.day!==t.dataset.day)}));"
          "document.documentElement.classList.add('js')</script>")
    return f'<div class=daytabs role=tablist>{tabs}</div>{"".join(panes)}{theme.FRESH_JS}{js}'


def build(M: pd.DataFrame, quotes: pd.DataFrame, board: pd.DataFrame, R: dict | None, stamp: str, remaining=None,
          totals: pd.DataFrame | None = None, extras: pd.DataFrame | None = None, record_html: str = "",
          record_tile: tuple[str, str] | None = None) -> str:
    e = html.escape
    present = [s for s in SITES if len(quotes) and s in set(quotes["site"])]
    n_flags = int(sum(1 for f in M["flag"] if f)) if len(M) else 0
    nw = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}.get(len(present), str(len(present)))

    # ---- today's best bets: per day, up to TOP_N results whose best price beats the fair price
    days = daily_picks(M, quotes, totals=totals, extras=extras)
    record_tile_html = (f'<a class=stat href="results.html" style="color:inherit;text-decoration:none"><div class=v>{e(record_tile[0])}</div>'
                        f'<div class=l>{e(record_tile[1]).replace(chr(10), "<br>")}</div></a>' if record_tile else
                        f"<div class=stat><div class=v>{sum(len(b) for _, b in days)}</div><div class=l>bets that beat what's expected</div></div>")
    picks_html = days_html(days)
    n_value = sum(len(b) for _, b in days)

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
                    best = np.isfinite(v) and v >= r[f"best_{o}"] - 1e-9            # best price among the sites: green text
                    good = np.isfinite(v) and v * r[f"cons_{o}"] > 1 + 1e-9         # pays more than Expected: green box
                    cls = " class='n" + (" best" if best else "") + (" good" if good else "") + "'"
                    cells += f"<td{cls}>{american(v)}</td>"
                body += f"<tr><td>{e(SITES[s][0])}</td>{cells}</tr>"
            body += ("<tr class=cons><td>Expected</td>" + "".join(
                f"<td class=n>{r[f'cons_us_{o}']} <small>({100 * r[f'cons_{o}']:.0f}%)</small></td>" for o in "hda") + "</tr>")
            blocks.append(f"""<div class=match><h4>{e(r['home'])} v {e(r['away'])} <small>· {_ko(r['kickoff'])}</small></h4>
<div class=tablewrap><table><tr><th>Site</th><th class=n>{e(r['home'])}</th><th class=n>Draw</th><th class=n>{e(r['away'])}</th></tr>{body}</table></div></div>""")
        nflag = int((G["flag"] != "").sum())
        leagues.append(f"<details class=league><summary>{e(lg)} <span>· {len(G)} matches"
                       f"</span></summary>{''.join(blocks)}</details>")

    return f"""<!doctype html><html lang=en><head>{theme.HEAD}
{theme.meta("", "Today's Soccer Bets", "Every morning: the soccer bets at FanDuel, DraftKings, BetMGM, Kalshi and Polymarket that pay more than their chance of winning deserves.")}
<style>{CSS}</style></head><body>
{theme.nav("week")}
<section class=hero><div class=wrap>
<p class=eyebrow>Updated every morning</p>
<h1>Bets that beat what's expected.</h1>
<p class=lede>Today's best-value soccer bets, and where to place them.</p>
<div class=ctas><a class=btn href="#best">See today's bets</a><a class="btn ghost" href="best-prices.html">Best price for every bet</a></div>
<p class=updated>Last updated {stamp}</p>
</div></section>

<section class=section id=best style="padding-bottom:0"><div class=wrap>
<h2>Ranked by expected return.</h2>
<p class=sub>Odds reflect each site’s implied probability plus its cut. By removing this cut and averaging the data across all {nw} sites, we estimate the true probability of an outcome. When a specific site offers higher payouts than this probability warrants, the wager appears below, ranked by value. The green figure represents your expected return per $100 wagered.</p>
<p class=note style="margin:-22px 0 22px">Kalshi and Polymarket odds are shown after their trading fee.</p>
</div></section>

<section class=band><div class=wrap>
<div class=stats>
<a class=stat href="best-prices.html" style="color:inherit;text-decoration:none"><div class=v>{len(M)}</div><div class=l>upcoming matches</div></a>
<a class=stat href="about.html#covered" style="color:inherit;text-decoration:none"><div class=v>{len(SITES)}</div><div class=l>sportsbooks and prediction markets</div></a>
<a class=stat href="#best" style="color:inherit;text-decoration:none"><div class=v id=nbets>{n_value}</div><div class=l id=nbets-l>upcoming bet{'' if n_value == 1 else 's'} paying more than {'it' if n_value == 1 else 'they'} should</div></a>
{record_tile_html}
</div></div></section>

<section class=section style="padding-top:18px"><div class=wrap>
{picks_html}
<p class=sub style="margin-top:18px"><b>Looking for a bet that isn't listed?</b> Most bets don't beat what's expected at any site, but one site still pays the most. <a href="best-prices.html">See the best price for every bet&nbsp;›</a></p>
</div></section>
{record_html}

<section class=section><div class=wrap>
<h2>Every match.</h2>
<p class=sub>+150 means a $100 bet wins $150; −200 means you bet $200 to win $100. Green text is the best price for each result. A green box means that price beats Expected, so it’s a good bet. Kalshi and Polymarket odds are shown after their trading fees, so they look slightly worse than on those apps. The "Expected" row shows each result's expected chance and the odds that would exactly match it.</p>
{''.join(leagues)}
</div></section>


{theme.footer()}
<script>(function(){{var n=document.querySelectorAll('li.bet-row').length,v=document.getElementById('nbets'),l=document.getElementById('nbets-l');
if(v){{v.textContent=n;l.textContent=n===1?'upcoming bet paying more than it should':'upcoming bets paying more than they should'}}}})()</script>
</body></html>"""
