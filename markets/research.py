"""The research page (docs/research.html): how accurate are soccer betting odds?

Built from output/results.json. The charts are interactive SVG drawn in the page (markets/viz.py).
Run: python -m markets.research
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import viz
from . import theme
from .website import LG, facts, p

ROOT = Path(__file__).resolve().parent.parent

EXTRA_CSS = """
.toc{display:grid;grid-template-columns:repeat(2,1fr);gap:10px 28px;padding:0;list-style:none;margin:0}
.toc a{color:var(--ink);font-size:17px;display:flex;gap:12px;align-items:baseline}.toc a:hover{color:var(--link);text-decoration:none}
.toc a b{color:var(--muted);font-size:13px;font-weight:600;font-variant-numeric:tabular-nums}
.finding{background:var(--bg2);border-radius:28px;padding:40px 40px 30px;margin:0 0 22px}
.finding .n{font-size:14px;font-weight:600;color:#bf4800;margin-bottom:6px}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .finding .n{color:#ff9f0a}}
:root[data-theme="dark"] .finding .n{color:#ff9f0a}
.finding h3{font-size:clamp(26px,3.4vw,34px);line-height:1.12;font-weight:700;letter-spacing:-.012em;margin:0 0 12px}
.finding .take{font-size:19px;line-height:1.42;color:var(--ink2);margin:0 0 22px;max-width:740px}
.finding p{color:var(--muted);font-size:17px;line-height:1.5;max-width:740px}
.finding .chart{background:var(--tile);border-radius:18px;padding:22px 22px 14px;margin:0 0 18px}
.finding table{min-width:0}.finding .tw{margin:12px 0}
.section ul.plain{color:var(--muted);padding-left:20px;max-width:760px}.section ul.plain li{margin:8px 0}
.section ul.plain b{color:var(--ink)}
.callout{max-width:760px;margin:26px auto 0;font-size:19px;line-height:1.45;color:var(--ink2)}
@media (max-width:720px){.toc{grid-template-columns:1fr}.finding{padding:26px 18px 18px;border-radius:22px}.finding .chart{padding:16px 12px 10px}}
"""


def dollars(x: float, signed: bool = False) -> str:
    """-0.064 -> '$6' (per $100 bet), or '−$6' / '+$6' when signed."""
    v = 100 * x
    if not signed:
        return f"${abs(v):.0f}"
    return f"−${-v:.0f}" if v <= -0.5 else (f"+${v:.0f}" if v >= 0.5 else "$0")


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
                  f"When the odds said {f['top_priced']}, it happened {f['top_happened']} of the time. "
                  f"When they said {f['low_priced']}, it happened {f['low_happened']} of the time.",
                  "<p>Favorites won slightly more often than their odds said, and long shots slightly less "
                  f"(calibration slope {c['slope']:.2f}, 95% range {c['slope_lo']:.2f} to {c['slope_hi']:.2f}; 1.00 is perfect).</p>",
                  viz.calibration(R["calibration"]["table"])))

    best = R["longshot"].get("best") or []
    items.append(("longshots", "Long shots are the worst bet",
                  f"Betting $100 on every heavy favorite ({fav_band}) lost {dollars(avg[0]['return'])} on average. "
                  f"Betting $100 on every long shot ({long_band}) lost {dollars(avg[-1]['return'])}.",
                  (f"<p>At the best price across bookmakers, heavy favorites returned {dollars(best[0]['return'], True)} per $100 "
                   f"and long shots {dollars(best[-1]['return'], True)}.</p>" if best else ""),
                  viz.longshot(avg)))

    items.append(("margins", "Bookmakers take a smaller cut than they used to",
                  f"The average bookmaker's margin fell from {f['margin_first']} in {R['seasons'][0][:4]} "
                  f"to {f['margin_last']} this season.", "",
                  viz.margins(R["margins"])))

    bs = R.get("by_season")
    if bs:
        t = bs["table"]
        worse = sum(r["longshot_return"] < r["fav_return"] for r in t)
        items.append(("still-longshots", "Long shots stayed the worse bet as margins fell",
                      f"Long shots lost more than favorites in {worse} of {len(t)} seasons.", "",
                      viz.longshot_by_season(t)))

    if R.get("closing"):
        items.append(("line-moves", "Prices that move before kick-off move the right way",
                      f"When the odds shortened before kick-off (chance up 3+ points), a $100 bet at the opening odds made "
                      f"{dollars(float(f['short_ret'].rstrip('%')) / 100, True)} on average. When they drifted, it lost "
                      f"{dollars(float(f['drift_ret'].rstrip('%')) / 100)}.",
                      f"<p>{f['cl_matches']} matches, {f['cl_years']}. Closing odds were more accurate than opening odds: "
                      f"error score {f['ll_close']} against {f['ll_open']} (lower is better).</p>",
                      viz.line_moves(R["closing"]["moves"])))

    mm = R["model"]
    sc = mm["scores"]
    names = {"uniform": "Equal chances (⅓ each)", "model": "Model from past results", "market": "The odds",
             "market_recalibrated": "The odds, recalibrated", "market_plus_model": "The odds and the model combined"}
    rows = "".join(f"<tr><td>{names.get(k, k)}</td><td class=num>{v['log_loss']:.3f}</td></tr>" for k, v in sc.items())
    items.append(("model", "A model built from past results can't beat the odds",
                  f"Error score (lower is better): the odds {sc['market']['log_loss']:.3f}, my model {sc['model']['log_loss']:.3f}, "
                  f"treating all three results as equally likely {sc['uniform']['log_loss']:.3f}.",
                  f"<div class=tw><table><tr><th>Forecast ({f['eval_matches']} matches from {f['eval_from']})</th><th class=num>Error score</th></tr>{rows}</table></div>"
                  f"<p>Betting $100 whenever my model rated a result 5%+ more likely than the odds: "
                  f"{dollars(float(f['vb_avg'].rstrip('%')) / 100, True)} a bet at the average price, "
                  f"{dollars(float(f['vb_best'].rstrip('%')) / 100, True)} at the best price.</p>",
                  viz.value_bets(curve) if curve is not None and len(curve) else ""))

    bl = {r["league"]: r for r in R.get("by_league", [])}
    if {"E0", "E1"} <= set(bl):
        e0, e1 = bl["E0"], bl["E1"]
        items.append(("leagues", "The second division is priced as accurately as the first",
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
                      f"<p>Slight favorites leading 1–0 at half-time were given a {P(lead['model_win'])} chance to win and won {P(lead['actual_win'])} "
                      f"of the time ({lead['matches']:,} matches). Games level at half-time were given a {P(lvl['model_draw'])} chance of a draw "
                      f"and ended level {P(lvl['actual_draw'])} of the time.</p>"
                      + checks,
                      viz.score_effects(lv["score_effects"])))

    toc, body = [], []
    for i, it in enumerate(items, 1):
        a, b = _finding(i, *it)
        toc.append(a)
        body.append(b)

    return f"""<!doctype html><html lang=en><head>{theme.HEAD}
{theme.meta("research.html", "How accurate are betting odds? · Today's Soccer Bets", "What 20 years of soccer betting odds show about how accurate the odds are and how much each bookmaker charges.")}
<meta name=description content="A test of soccer betting odds on {f['matches']} matches: how accurate they are, where they go wrong, and whether a model can beat them.">
<style>{theme.CSS}{EXTRA_CSS}{viz.CSS}</style></head><body>
{theme.nav("research")}
<section class=hero><div class=wrap>
<p class=eyebrow>Research</p>
<h1>How accurate are betting odds?</h1>
<p class=lede>I tested betting odds on {f['matches']} matches
from the {f['leagues']}, every season since {R['seasons'][0][:4]}.</p>
<div class=ctas><a class=btn href="#found">See the findings</a><a class="btn ghost" href="index.html">This week's best bets</a></div>
</div></section>

<section class=band><div class=wrap>
<div class=stats>
<div class=stat><div class=v>{f['matches']}</div><div class=l>matches tested</div></div>
<div class=stat><div class=v>{f['n_seasons']}</div><div class=l>seasons</div></div>
<div class=stat><div class=v>{dollars(avg[-1]['return'])}</div><div class=l>lost per $100 on long shots</div></div>
<div class=stat><div class=v>{f['margin_last']}</div><div class=l>bookmaker's cut today, down from {f['margin_first']}</div></div>
</div></div></section>

<section class=section id=found><div class=wrap>
<h2>What I found.</h2>
<ul class=toc>{''.join(toc)}</ul>
</div></section>
<div class=wrap>{''.join(body)}</div>

<section class=band><div class=wrap>
<h2>How it's built.</h2>
<ul class=plain>
<li><b>Data.</b> Results and odds from up to ten bookmakers per match, from <a href="https://www.football-data.co.uk">football-data.co.uk</a>.</li>
<li><b>Removing the margin.</b> Three methods compared: proportional, power and Shin's 1993 model.</li>
<li><b>Model.</b> Team ratings refitted every week on past matches only, in scikit-learn.</li>
<li><b>Uncertainty.</b> 95% ranges from resampling whole matches (the bootstrap).</li>
<li><b>Tests.</b> Automated checks, including one that the model never sees a match before predicting it.</li>
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
