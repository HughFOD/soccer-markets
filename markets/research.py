"""The research page (docs/research.html): how accurate are football betting odds?

Built from output/results.json. The charts are interactive SVG drawn in the page (markets/viz.py).
Run: python -m markets.research
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import viz
from .website import CSS, LG, REPO_URL, facts, p

ROOT = Path(__file__).resolve().parent.parent

EXTRA_CSS = """
.cta{display:inline-block;margin-top:22px;background:#eb6834;color:#fff;font-weight:600;padding:10px 18px;border-radius:8px;text-decoration:none}
.toc{display:grid;grid-template-columns:repeat(2,1fr);gap:8px 18px;padding:0;list-style:none;margin:8px 0 0}
.toc a{text-decoration:none;color:var(--ink)}.toc a b{color:var(--accent);font:600 12px 'JetBrains Mono',monospace;margin-right:8px}
.finding h3{font-size:1.25rem}
.finding .take{font-size:1.02rem;color:var(--ink);margin:4px 0 10px}
.tw{overflow-x:auto}.finding table{min-width:0}
@media (max-width:720px){.toc{grid-template-columns:1fr}.finding{padding:18px 14px 10px}td,th{padding:7px 4px;font-size:.86rem}}
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

    items.append(("accurate", "The odds are accurate",
                  f"Results the odds gave a {f['top_priced']} chance happened {f['top_happened']} of the time. "
                  f"Results given a {f['low_priced']} chance happened {f['low_happened']} of the time.",
                  "<p>I grouped every result by the chance its odds implied, then checked how often it happened. "
                  "The dots sit almost on the line, so the odds are very good forecasts. They miss slightly in one direction: "
                  "favourites win a little more often than the odds say, and long shots a little less.</p>",
                  viz.calibration(R["calibration"]["table"])))

    items.append(("longshots", "Long shots are the worst bet",
                  f"Betting $100 on every heavy favourite ({fav_band}) lost {dollars(avg[0]['return'])} on average. "
                  f"Betting $100 on every long shot ({long_band}) lost {dollars(avg[-1]['return'])}.",
                  "<p>Bookmakers build more of their cut into long shots, because bettors like them and rarely notice. "
                  "This favourite–long-shot bias also shows up in horse racing and other betting markets. "
                  "Taking the best price across about ten bookmakers gets favourites close to breaking even, "
                  "but that means holding an account with every one of them.</p>",
                  viz.longshot(avg)))

    items.append(("margins", "Bookmakers take a smaller cut than they used to",
                  f"The average bookmaker's margin fell from {f['margin_first']} in {R['seasons'][0][:4]} "
                  f"to {f['margin_last']} this season.",
                  "<p>The margin is the bookmaker's built-in cut: add up the chances the odds give a home win, a draw and an away win, "
                  "and the total is a little over 100%. Online competition has pushed it down steadily.</p>",
                  viz.margins(R["margins"])))

    bs = R.get("by_season")
    if bs:
        t = bs["table"]
        worse = sum(r["longshot_return"] < r["fav_return"] for r in t)
        items.append(("still-longshots", "Cheaper betting didn't fix the long-shot problem",
                      f"Long shots were the worse bet in {worse} of {len(t)} seasons, even as margins fell.",
                      "<p>If smaller margins meant fairer prices across the board, the two lines would have come together. "
                      "They didn't: favourites got close to break-even, and long shots kept losing.</p>",
                      viz.longshot_by_season(t)))

    if R.get("closing"):
        items.append(("line-moves", "Prices that move before kick-off move the right way",
                      f"When a result's chance rose 3+ points before kick-off, a $100 bet at the opening price made "
                      f"{dollars(float(f['short_ret'].rstrip('%')) / 100, True)}. When it fell, the bet lost "
                      f"{dollars(float(f['drift_ret'].rstrip('%')) / 100)}.",
                      f"<p>The data has an opening price and a closing price (just before kick-off) for {f['cl_matches']} matches "
                      f"from {f['cl_years']}, and the closing price was the better forecast. This isn't a strategy, because you can't "
                      "know the move in advance. It shows that team news and injuries arrive before kick-off and the opening price "
                      "hasn't caught up yet. Other cut-offs, not just 3 points, point the same way.</p>",
                      viz.line_moves(R["closing"]["moves"])))

    mm = R["model"]
    sc = mm["scores"]
    names = {"uniform": "Equal chances (⅓ each)", "model": "My model", "market": "The odds",
             "market_recalibrated": "The odds, slightly adjusted", "market_plus_model": "The odds and my model combined"}
    rows = "".join(f"<tr><td>{names.get(k, k)}</td><td class=num>{v['log_loss']:.3f}</td></tr>" for k, v in sc.items())
    items.append(("model", "A model built from past results can't beat the odds",
                  f"My model was much better than guessing, but clearly worse than the odds, and adding it to the odds didn't help.",
                  f"<p>The model rates each team's attack and defence from its recent goals (Dixon and Coles, 1997). Every week it is refitted "
                  f"on matches already played, so it never sees the future. Its one setting was chosen on seasons before 2008 and then left alone.</p>"
                  f"<div class=tw><table><tr><th>Forecast ({f['eval_matches']} matches from {f['eval_from']})</th><th class=num>Error score (lower is better)</th></tr>{rows}</table></div>"
                  f"<p>Betting $100 on every result the model rated at least 5% more likely than the odds lost "
                  f"{dollars(float(f['vb_avg'].rstrip('%')) / 100)} a bet at the average price. Even at the best price available, "
                  f"it only roughly broke even ({dollars(float(f['vb_best'].rstrip('%')) / 100, True)} a bet).</p>",
                  viz.value_bets(curve) if curve is not None and len(curve) else ""))

    bl = {r["league"]: r for r in R.get("by_league", [])}
    if {"E0", "E1"} <= set(bl):
        e0, e1 = bl["E0"], bl["E1"]
        items.append(("leagues", "The second division isn't easier to beat",
                      "Less money is bet on the Championship than the Premier League, but its odds are just as accurate.",
                      f"<div class=tw><table><tr><th>League</th><th class=num>Matches</th><th class=num>Margin</th><th class=num>Betting $100 on everything</th></tr>"
                      f"<tr><td>Premier League</td><td class=num>{e0['matches']:,}</td><td class=num>{p(e0['margin'], 1, False)}</td><td class=num>{dollars(e0['bet_everything'], True)}</td></tr>"
                      f"<tr><td>Championship</td><td class=num>{e1['matches']:,}</td><td class=num>{p(e1['margin'], 1, False)}</td><td class=num>{dollars(e1['bet_everything'], True)}</td></tr></table></div>"
                      "<p>My model didn't help in either league.</p>"))

    lv = R.get("live")
    if lv:
        se = {r["margin"]: r for r in lv["score_effects"]}
        st = {(r["favourite"], r["half_time"]): r for r in lv["by_state"]}
        lead = st[("narrow favourite", "leading by 1")]
        lvl = st[("narrow favourite", "level")]
        rb = lv.get("robustness") or []
        checks = ""
        if rb:
            checks = (f"<p><b>Is it really the scoreline?</b> Maybe games with early goals are just more open. To rule that out, I compared "
                      f"the two teams in the same match, which cancels out anything that affects both sides. The pattern holds in "
                      f"{'all ' + str(len(rb)) if all(r['ratio'] > 1 for r in rb) else str(sum(r['ratio'] > 1 for r in rb)) + ' of ' + str(len(rb))} checks: "
                      "with or without red cards, in both decades, in both English leagues, and after quiet or busy first halves.</p>"
                      + viz.score_checks(rb))
        items.append(("half-time", "After half-time, the team that's behind scores more than expected",
                      f"Teams losing by 2+ at half-time scored {p(se[-2]['ratio'] - 1, 0, False)} more in the second half than the odds "
                      f"predicted. Teams winning by 2+ scored {p(1 - se[2]['ratio'], 0, False)} fewer.",
                      "<p>The simplest way to price a match at half-time is to assume both teams keep scoring at the rate the pre-match odds "
                      "expected. That's wrong: teams that are behind push forward, and teams that are ahead sit back.</p>"
                      f"<p>So that simple price overrates the team in front. A slight favourite leading 1–0 at half-time was given a "
                      f"{p(lead['model_win'], 0, False)} chance of winning and won {p(lead['actual_win'], 0, False)} of the time. Games level at "
                      f"half-time ended in a draw {p(lvl['actual_draw'], 0, False)} of the time, not the {p(lvl['model_draw'], 0, False)} predicted. "
                      "The data has no live odds, so this shows where a simple live price goes wrong, not whether bookmakers make the same mistake.</p>"
                      + checks,
                      viz.score_effects(lv["score_effects"])))

    toc, body = [], []
    for i, it in enumerate(items, 1):
        a, b = _finding(i, *it)
        toc.append(a)
        body.append(b)

    return f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>How Accurate Are Betting Odds?</title>
<meta name=description content="A test of football betting odds on {f['matches']} matches: how accurate they are, where they go wrong, and whether a model can beat them.">
<link rel=preconnect href=https://fonts.googleapis.com><link rel=preconnect href=https://fonts.gstatic.com crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700&family=Instrument+Sans:wght@400;500;600&family=JetBrains+Mono:wght@500;600&display=swap" rel=stylesheet>
<style>{CSS}{EXTRA_CSS}{viz.CSS}</style></head><body>
<header class=hero><div class=wrap>
<div class=kicker>Background research · Python</div>
<h1>How Accurate Are Football Betting Odds?</h1>
<p class=lede>Odds are forecasts: +150 says a result has about a 40% chance. I tested those forecasts on {f['matches']} matches
from the {f['leagues']}, every season since {R['seasons'][0][:4]}.</p>
<div class=result><b>In short</b>The odds are very accurate and a model built from past results couldn't beat them.
But they have blind spots: long shots are overpriced, the opening price is slow to react to news, and the simple
way to price a game at half-time overrates the team that's ahead.</div>
<a class=cta href="index.html">← Back to this week's odds comparison</a>
<p class=note><code>Odds</code> +150 means a $100 bet wins $150; −200 means you bet $200 to win $100. The data is from
European bookmakers, because free historical odds from American sites don't exist.</p>
</div></header>
<main class=wrap>
<div class=stats>
<div class=stat><div class=v>{f['matches']}</div><div class=l>matches tested</div></div>
<div class=stat><div class=v>{f['n_seasons']}</div><div class=l>seasons</div></div>
<div class=stat><div class=v>{dollars(avg[-1]['return'])}</div><div class=l>lost per $100 on long shots</div></div>
<div class=stat><div class=v>{f['margin_last']}</div><div class=l>bookmaker's cut today, down from {f['margin_first']}</div></div>
</div>

<h2>What I found</h2>
<ul class=toc>{''.join(toc)}</ul>
{''.join(body)}

<h2>What I learned</h2>
<div class=cards>
<div class=card><h3>Judge the chances, not the picks</h3><p>Counting how often a forecast picks the winner throws away most of the information. An error score rewards a forecast for being confident only when it should be.</p></div>
<div class=card><h3>Never let the model see the future</h3><p>The model only uses matches already played, and its setting was chosen on separate early seasons. Without that, a backtest can look profitable by accident.</p></div>
<div class=card><h3>Always show the uncertainty</h3><p>Betting results are noisy. Several strategies that looked promising here turned out to be luck once the uncertainty was measured.</p></div>
</div>

<h2>How it's built</h2>
<ul>
<li><b>Data:</b> results and odds from up to ten bookmakers per match, from <a href="https://www.football-data.co.uk">football-data.co.uk</a>.</li>
<li><b>Removing the margin:</b> three methods compared (proportional, power and Shin's 1993 model).</li>
<li><b>Model:</b> team ratings refitted every week on past matches only, in scikit-learn.</li>
<li><b>Uncertainty:</b> 95% ranges from resampling whole matches (the bootstrap).</li>
<li><b>Tests:</b> automated checks, including one that the model never sees a match before predicting it.</li>
</ul>
<h2>Limits</h2>
<ul>
<li>The odds are snapshots collected by football-data.co.uk, not every price on offer.</li>
<li>The history is European bookmakers; American sites may price differently.</li>
<li>This is a study of forecasting, not betting advice. Mostly, it shows how hard the market is to beat.</li>
</ul>
</main>
<footer><div class=wrap>Code and data: <a href="{REPO_URL}">{REPO_URL.replace('https://', '')}</a></div></footer>
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
