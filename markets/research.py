"""The research page (docs/research.html): how accurate are soccer betting odds?

Built from output/results.json. The charts are interactive SVG drawn in the page (markets/viz.py).
Run: python -m markets.research
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from . import viz
from . import theme
from .website import LG, facts, p

ROOT = Path(__file__).resolve().parent.parent

EXTRA_CSS = """
.toc{columns:2;column-gap:28px;padding:0;list-style:none;margin:0}.toc li{break-inside:avoid;margin-bottom:10px}
.toc a{color:var(--ink);font-size:16px;display:flex;gap:12px;align-items:baseline}.toc a:hover{color:var(--link);text-decoration:none}
.toc a b{color:var(--muted);font-size:13px;font-family:var(--mono);font-weight:600;font-variant-numeric:tabular-nums}
.finding{background:var(--tile);border:1px solid var(--line);border-top:3px solid var(--ink);border-radius:var(--r);padding:26px 28px 20px;margin:0 0 22px}
.finding .n{font:600 12px var(--mono);color:var(--link);margin-bottom:6px;letter-spacing:.06em}
.finding h3{font-size:clamp(21px,2.6vw,26px);line-height:1.2;font-weight:700;margin:0 0 10px}
.finding .take{font-size:17px;line-height:1.5;color:var(--ink2);margin:0 0 22px}
.finding p{color:var(--muted);font-size:15px;line-height:1.55}
.finding .chart{background:var(--tile);border:1px solid var(--hair);border-radius:var(--r);padding:22px 22px 14px;margin:0 0 18px}
.finding table{min-width:0}.finding .tw{margin:12px 0}
.section ul.plain{color:var(--muted);padding-left:20px}.section ul.plain li{margin:8px 0}
.section ul.plain b{color:var(--ink)}
.callout{max-width:760px;margin:26px auto 0;font-size:19px;line-height:1.45;color:var(--ink2)}
@media (max-width:720px){.toc{columns:1}.finding{padding:26px 18px 18px;border-radius:var(--r)}.finding .chart{padding:16px 12px 10px}}
"""


def dollars(x: float, signed: bool = False) -> str:
    """-0.064 -> '$6' (per $100 bet), or '−$6' / '+$6' when signed."""
    v = 100 * x
    if not signed:
        return f"${abs(v):.0f}"
    return f"−${-v:.0f}" if v <= -0.5 else (f"+${v:.0f}" if v >= 0.5 else "$0")


def an(s: str) -> str:
    """'a' or 'an' before a percentage: an 80%, an 11%, an 18%, a 70%."""
    s = str(s).lstrip()
    return "an" if s.startswith("8") or re.match(r"1[18](\D|$)", s) else "a"


def _finding(n: int, slug: str, title: str, take: str, body: str, pic: str = "") -> tuple[str, str]:
    return (f'<li><a href="#{slug}"><b>{n:02d}</b>{title}</a></li>',
            f'<div class=finding id="{slug}"><div class=n>FINDING {n}</div><h3>{title}</h3>'
            f'<p class=take>{take}</p>{pic}{body}</div>')


def build(R: dict, curve: pd.DataFrame | None = None) -> str:
    f = facts(R)
    avg = R["longshot"]["average"]
    fav_band = viz.band_label(avg[0]["odds"])
    long_band = viz.band_label(avg[-1]["odds"])
    items = []
    P = lambda x: p(x, 0, False)   # 0.237 -> '24%'

    c = R["calibration"]["pooled"]
    items.append(("accurate", "The odds are accurate",
                  f"Strong favorites that the odds gave {an(f['top_priced'])} {f['top_priced']} chance of winning actually won "
                  f"{f['top_happened']} of the time. Long shots given {an(f['low_priced'])} {f['low_priced']} chance won "
                  f"{f['low_happened']} of the time. So the odds are close to the truth.",
                  "<p>They're slightly off in one consistent way: favorites win a little more often than their odds "
                  "suggest, and long shots a little less. (Technically, a calibration slope of "
                  f"{c['slope']:.2f}, 95% range {c['slope_lo']:.2f} to {c['slope_hi']:.2f}, where 1.00 would be perfect.)</p>",
                  viz.calibration(R["calibration"]["table"])))

    best = R["longshot"].get("best") or []
    items.append(("longshots", "Long shots are the worst bet",
                  f"Betting $100 on every heavy favorite ({fav_band}) lost {dollars(avg[0]['return'])} on average. "
                  f"Betting $100 on every long shot ({long_band}) lost {dollars(avg[-1]['return'])}.",
                  (f"<p>At the best price across bookmakers, heavy favorites returned {dollars(best[0]['return'], True)} per $100 "
                   f"and long shots {dollars(best[-1]['return'], True)}.</p>" if best else ""),
                  viz.longshot(avg)))


    if R.get("closing"):
        cl = R["closing"]
        top = max(m["threshold"] for m in cl["moves"])
        mv = {m["direction"]: m for m in cl["moves"] if abs(m["threshold"] - top) < 1e-9}
        every = cl.get("bet_all_open")
        items.append(("line-moves", "When odds change before kick-off, they're usually right to do so",
                      f"Odds move as news comes in. The bigger the move, the more it mattered: when a team's chance rose by "
                      f"{100 * top:.0f} or more percentage points before the match (say, from 40% to {40 + 100 * top:.0f}%), "
                      f"an early $100 bet on it made {dollars(mv['shortened']['return'], True)}. When its chance fell by "
                      f"{100 * top:.0f} or more, the same bet lost {dollars(mv['drifted']['return'])}."
                      + (f" Betting every result at the first odds lost {dollars(every['return'])}." if every else "")
                      + " That's why every pick on this site is checked again at kick-off.",
                      f"<p>Late news, like injuries and team sheets, moves the odds in the right direction. "
                      f"The odds at kick-off were also more accurate than the first odds offered "
                      f"(error score {f['ll_close']} against {f['ll_open']}; lower is better). "
                      f"Based on {f['cl_matches']} matches, {f['cl_years']}.</p>",
                      viz.line_moves(cl["moves"], every)))

    bl = {r["league"]: r for r in R.get("by_league", [])}
    if {"E0", "E1"} <= set(bl):
        e0, e1 = bl["E0"], bl["E1"]
        items.append(("leagues", "England’s second division is priced as accurately as the first",
                      f"Calibration slope (1.00 is perfect): {e0['slope']:.2f} in the Premier League, {e1['slope']:.2f} in the Championship.",
                      f"<div class=tw><table><tr><th>League</th><th class=num>Matches</th><th class=num>Margin</th><th class=num>Slope</th><th class=num>Betting $100 on everything</th></tr>"
                      f"<tr><td>Premier League</td><td class=num>{e0['matches']:,}</td><td class=num>{p(e0['margin'], 1, False)}</td><td class=num>{e0['slope']:.2f}</td><td class=num>{dollars(e0['bet_everything'], True)}</td></tr>"
                      f"<tr><td>Championship</td><td class=num>{e1['matches']:,}</td><td class=num>{p(e1['margin'], 1, False)}</td><td class=num>{e1['slope']:.2f}</td><td class=num>{dollars(e1['bet_everything'], True)}</td></tr></table></div>"))

    lv = R.get("live")
    if lv:
        se = {r["margin"]: r for r in lv["score_effects"]}
        st = {(r["favourite"], r["half_time"]): r for r in lv["by_state"]}
        lead = st[("narrow favourite", "leading by 1")]
        lvl = st[("narrow favourite", "level")]
        rb = lv.get("robustness") or []
        allr = next((r for r in rb if r["check"].startswith("All matches")), None)
        checks = ""
        if rb:
            n_ok = sum(r["ratio"] > 1 for r in rb)
            checks = ((f"<p>In the second half, the team that was behind was expected to score {p(allr['expected_share'], 1, False)} "
                       f"of the goals and scored {p(allr['actual_share'], 1, False)}. " if allr else "<p>")
                      + f"This held in {n_ok} of {len(rb)} checks.</p>" + viz.score_checks(rb))
        items.append(("half-time", "After half-time, the team that's behind scores more than expected",
                      f"Teams losing by 2+ at half-time scored {P(se[-2]['ratio'] - 1)} more in the second half than the odds "
                      f"predicted. Teams winning by 2+ scored {P(1 - se[2]['ratio'])} fewer.",
                      f"<p>Slight favorites leading 1–0 at half-time were given {an(P(lead['model_win']))} {P(lead['model_win'])} chance to win and won {P(lead['actual_win'])} "
                      f"of the time ({lead['matches']:,} matches). Games level at half-time were given {an(P(lvl['model_draw']))} {P(lvl['model_draw'])} chance of a draw "
                      f"and ended level {P(lvl['actual_draw'])} of the time.</p>"
                      + checks,
                      viz.score_effects(lv["score_effects"])))

    order = ["accurate", "longshots", "half-time", "line-moves", "leagues"]
    items.sort(key=lambda it: order.index(it[0]) if it[0] in order else len(order))
    toc, body = [], []
    for i, it in enumerate(items, 1):
        a, b = _finding(i, *it)
        toc.append(a)
        body.append(b)

    return f"""<!doctype html><html lang=en><head>{theme.HEAD}
{theme.meta("research.html", "How accurate are betting odds? · Today's Soccer Bets", f"What {int(R['seasons'][-1][:4]) - int(R['seasons'][0][:4])} years of soccer betting odds show about how accurate the odds are.")}
<style>{theme.CSS}{EXTRA_CSS}{viz.CSS}</style></head><body>
{theme.nav("research")}
<section class=hero><div class=wrap>
<p class=eyebrow>Research</p>
<h1>How accurate are betting odds?</h1>
<p class=lede>{f['matches']} matches from six top European leagues since {R['seasons'][0][:4]}, checked against their betting odds.</p>
<div class=ctas><a class=btn href="#found">See the findings</a><a class="btn ghost" href="index.html">Today's best bets</a></div>
</div></section>

<section class=section id=found><div class=wrap>
<h2>What I found.</h2>
<ul class=toc>{''.join(toc)}</ul>
</div></section>
<div class=wrap>{''.join(body)}</div>

<section class=band><div class=wrap>
<h2>How it's built.</h2>
<ul class=plain>
<li><b>Data.</b> Results and odds from every bookmaker recorded for each match, from <a href="https://www.football-data.co.uk">football-data.co.uk</a>.</li>
<li><b>Removing the cut.</b> Three methods compared: proportional, power and Shin's 1993 model.</li>
<li><b>Uncertainty.</b> 95% ranges from resampling whole matches (the bootstrap).</li>
<li><b>Tests.</b> Automated checks on every calculation.</li>
<li><b>Odds.</b> Snapshots from European bookmakers collected by football-data.co.uk.</li>
</ul>
</div></section>
{theme.footer()}
<script>{viz.JS}</script>
</body></html>"""


def main(out_dir: Path = ROOT / "output", docs: Path = ROOT / "docs"):
    R = json.loads((out_dir / "results.json").read_text())
    cf = out_dir / "value_bet_curve.csv"
    curve = pd.read_csv(cf) if cf.exists() else None
    (docs / "research.html").write_text(build(R, curve))
    print(f"wrote {docs / 'research.html'}")


if __name__ == "__main__":
    main()
