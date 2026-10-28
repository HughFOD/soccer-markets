"""Build docs/index.html (the GitHub Pages site) from output/results.json.

Run: python -m markets.website
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_URL = "https://github.com/HughFOD/soccer-markets"
CHARTS = ("calibration", "longshot", "margins", "line_moves", "value_bets", "soft_vs_sharp", "slope_by_season", "score_effects")


def p(x, d=1, sign=True):
    return f"{100 * x:+.{d}f}%" if sign else f"{100 * x:.{d}f}%"


def facts(R: dict) -> dict:
    c = R["calibration"]
    t = c["table"]
    avg = R["longshot"]["average"]
    mg = R["margins"]
    cl = R["closing"]
    mm = R["model"]
    bets = {(b["forecast"], b["odds"], b["edge"]): b for b in mm["bets"]}
    methods = {r["method"]: r for r in R["margin_methods"]}
    f = {
        "matches": f"{R['matches']:,}",
        "years": f"{R['seasons'][0][:4]} to {R['seasons'][1][-4:]}",
        "n_seasons": len(mg),
        "leagues": " and ".join({"E0": "Premier League", "E1": "Championship"}.get(x, x) for x in R["leagues"]),
        "slope": f"{c['pooled']['slope']:.2f}", "slope_lo": f"{c['pooled']['slope_lo']:.2f}",
        "slope_hi": f"{c['pooled']['slope_hi']:.2f}",
        "top_priced": p(t[-1]["priced"], 0, False), "top_happened": p(t[-1]["happened"], 0, False),
        "low_priced": p(t[0]["priced"], 0, False), "low_happened": p(t[0]["happened"], 0, False),
        "fav_ret": p(avg[0]["return"]), "long_ret": p(avg[-1]["return"]), "long_band": avg[-1]["odds"],
        "power_slope": f"{methods['power']['slope']:.2f}", "prop_slope": f"{methods['proportional']['slope']:.2f}",
        "margin_first": p(mg[0]["avg_margin"], 1, False), "margin_last": p(mg[-1]["avg_margin"], 1, False),
        "pin_margin": p(sorted(x["pin_margin"] for x in mg if x["pin_margin"])[len([x for x in mg if x["pin_margin"]]) // 2], 1, False),
        "model_ll": f"{mm['scores']['model']['log_loss']:.3f}", "market_ll": f"{mm['scores']['market']['log_loss']:.3f}",
        "uniform_ll": f"{mm['scores']['uniform']['log_loss']:.3f}",
        "eval_matches": f"{mm['matches']:,}", "eval_from": mm["eval_from"][:4],
        "gain": f"{-mm['gain_from_model'][0]:+.4f}", "gain_lo": f"{-mm['gain_from_model'][2]:+.4f}",
        "gain_hi": f"{-mm['gain_from_model'][1]:+.4f}",
        "vb_avg": p(bets[("model", "avg", 0.05)]["return"]), "vb_pin": p(bets[("model", "pin", 0.05)]["return"]),
        "vb_best": p(bets[("model", "best", 0.05)]["return"]),
        "vb_avg_lo": p(bets[("model", "avg", 0.05)]["lo"]), "vb_avg_hi": p(bets[("model", "avg", 0.05)]["hi"]),
        "half_life": R["model_tuning"]["half_life_days"],
    }
    if cl:
        mv = {(r["threshold"], r["direction"]): r for r in cl["moves"]}
        s, d = mv[(0.03, "shortened")], mv[(0.03, "drifted")]
        f.update(cl_matches=f"{cl['matches']:,}", ll_open=f"{cl['log_loss_open']:.4f}", ll_close=f"{cl['log_loss_close']:.4f}",
                 short_ret=p(s["return"]), short_lo=p(s["lo"]), short_hi=p(s["hi"]), short_n=f"{s['bets']:,}",
                 drift_ret=p(d["return"]), drift_lo=p(d["lo"]), drift_hi=p(d["hi"]),
                 cl_years=f"{cl['seasons'][0][:4]} to {cl['seasons'][-1][-4:]}")
    return f


CSS = """
:root{--bg:#fbfaf7;--ink:#14161a;--ink2:#4a4d55;--muted:#767a83;--line:#e3e1db;--card:#ffffff;--accent:#2a78d6;--accent2:#eb6834;--hero:#101722;--heroink:#eef1f6}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#121417;--ink:#eceef2;--ink2:#b7bbc4;--muted:#8a8f99;--line:#2a2e35;--card:#1a1d22;--accent:#3987e5;--accent2:#d95926;--hero:#0b0f16}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.65 'Instrument Sans',system-ui,sans-serif}
.wrap{max-width:900px;margin:0 auto;padding:0 20px}
header.hero{background:var(--hero);color:var(--heroink);padding:56px 0 44px}
.kicker{font:500 12px/1 'JetBrains Mono',monospace;letter-spacing:.12em;text-transform:uppercase;color:#9fb4d4}
h1{font:700 clamp(1.6rem,2.9vw,2.3rem)/1.2 Archivo,system-ui,sans-serif;margin:14px 0 18px;letter-spacing:-.01em}
.lede{font-size:1.08rem;color:#d3d9e3;max-width:760px}
.result{margin-top:26px;border-left:3px solid var(--accent2);padding:10px 0 10px 18px;max-width:760px}
.result b{display:block;font:600 12px/1.4 'JetBrains Mono',monospace;letter-spacing:.1em;text-transform:uppercase;color:#f3a37f;margin-bottom:4px}
.note{margin-top:22px;font-size:.92rem;color:#aab4c3;max-width:760px}
.note code{font-family:'JetBrains Mono',monospace;background:#1d2633;padding:1px 6px;border-radius:4px;color:#e6ebf2}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line);border-radius:10px;overflow:hidden;margin:-22px 0 40px;position:relative}
.stat{background:var(--card);padding:16px 18px}.stat .v{font:700 1.5rem/1.1 Archivo,sans-serif}.stat .l{font-size:.82rem;color:var(--muted);margin-top:4px}
h2{font:700 1.45rem/1.25 Archivo,sans-serif;margin:52px 0 12px}
h3{font:650 1.1rem/1.35 Archivo,sans-serif;margin:0 0 6px}
.finding{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:22px 22px 14px;margin:18px 0}
.finding .n{font:600 12px 'JetBrains Mono',monospace;color:var(--accent);letter-spacing:.1em}
.finding img{width:100%;height:auto;border-radius:6px;margin:10px 0 6px;background:#fff}
.finding p{margin:6px 0 10px;color:var(--ink2)}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px}.card p{margin:0;color:var(--ink2);font-size:.95rem}
table{border-collapse:collapse;width:100%;font-size:.93rem;margin:10px 0}td,th{border-bottom:1px solid var(--line);padding:8px 6px;text-align:left}th{color:var(--muted);font-weight:600}
td.num,th.num{text-align:right;font-family:'JetBrains Mono',monospace}
ul{padding-left:20px;color:var(--ink2)}li{margin:4px 0}
a{color:var(--accent)}footer{border-top:1px solid var(--line);margin-top:56px;padding:26px 0 40px;color:var(--muted);font-size:.9rem}
@media (max-width:720px){.stats{grid-template-columns:repeat(2,1fr)}.cards{grid-template-columns:1fr}}
"""


def more_findings(R: dict, start: int) -> str:
    """Findings from markets/sharp.py: Pinnacle vs retail bookmakers, change over time, league comparison."""
    html, n = [], start
    sh, sb = R.get("sharp"), R.get("soft_bets")
    if sh and sb:
        rules = {r["edge"]: r for r in sb["rules"]}
        r0, r2 = rules[0.0], rules[0.02]
        d = sh["average_minus_pinnacle"]
        html.append(f"""
<div class=finding><div class=n>FINDING {n}</div>
<h3>Pinnacle's price can find generous retail prices, but the evidence is weak</h3>
<p>Pinnacle charges a margin of {p(sh['margin_pinnacle'], 1, False)}; the average bookmaker charges {p(sh['margin_average'], 1, False)}. With the margin removed, the two are equally accurate (log loss {sh['log_loss_pinnacle']:.4f} against {sh['log_loss_average']:.4f}), and the average adds nothing to Pinnacle.</p>
<p>Retail bookmakers do not all move their prices at once, so sometimes one offers better odds than Pinnacle's fair price. Betting only those prices returned {p(r0['return'])} per bet (95% interval {p(r0['lo'])} to {p(r0['hi'])}, {r0['bets']:,} bets over {sb['matches']:,} matches). When the retail price was at least 2% better, the return was {p(r2['return'])} ({p(r2['lo'])} to {p(r2['hi'])}).</p>
<img src="images/soft_vs_sharp.png" alt="Return from retail prices that beat Pinnacle's fair price">
<p>Every estimate is positive and close to what Pinnacle's price predicted, but every interval touches zero, and most of the profit came in 2012–2014. In practice, retail bookmakers limit customers who do this.</p></div>""")
        n += 1
    bs = R.get("by_season")
    if bs:
        t = bs["table"]
        tr = bs["slope_trend_per_decade"]
        html.append(f"""
<div class=finding><div class=n>FINDING {n}</div>
<h3>Margins fell, but the long-shot bias did not</h3>
<p>Measured season by season, the calibration slope shows no clear trend: {tr[0]:+.2f} per decade (standard error {tr[1]:.2f}). Long shots were overpriced in {sum(r['longshot_return'] < r['fav_return'] for r in t)} of {len(t)} seasons. Cheaper betting did not make the prices more accurate.</p>
<img src="images/slope_by_season.png" alt="Calibration slope by season"></div>""")
        n += 1
    bl = {r["league"]: r for r in R.get("by_league", [])}
    if {"E0", "E1"} <= set(bl):
        e0, e1 = bl["E0"], bl["E1"]
        g = R["model"].get("by_league", {})
        html.append(f"""
<div class=finding><div class=n>FINDING {n}</div>
<h3>The Championship is not priced less efficiently</h3>
<p>I expected the second division, with less attention and smaller bets, to be easier to beat. It was not. Its calibration slope ({e1['slope']:.2f}, interval {e1['slope_lo']:.2f}–{e1['slope_hi']:.2f}) is no further from 1 than the Premier League's ({e0['slope']:.2f}, {e0['slope_lo']:.2f}–{e0['slope_hi']:.2f}), and the model from past scores added nothing in either league.</p>
<table><tr><th>League</th><th class=num>Matches</th><th class=num>Margin</th><th class=num>Calibration slope</th><th class=num>Bet everything</th></tr>
<tr><td>Premier League</td><td class=num>{e0['matches']:,}</td><td class=num>{p(e0['margin'], 1, False)}</td><td class=num>{e0['slope']:.2f}</td><td class=num>{p(e0['bet_everything'])}</td></tr>
<tr><td>Championship</td><td class=num>{e1['matches']:,}</td><td class=num>{p(e1['margin'], 1, False)}</td><td class=num>{e1['slope']:.2f}</td><td class=num>{p(e1['bet_everything'])}</td></tr></table></div>""")
        n += 1
    lv = R.get("live")
    if lv:
        se = {r["margin"]: r for r in lv["score_effects"]}
        st = {(r["favourite"], r["half_time"]): r for r in lv["by_state"]}
        lead = st.get(("narrow favourite", "leading by 1"))
        lvl = st.get(("narrow favourite", "level"))
        g = lv["adjusted_gain"]
        html.append(f"""
<div class=finding><div class=n>FINDING {n}</div>
<h3>In-play: a half-time lead is less safe than a simple model thinks</h3>
<p>The data have half-time scores, so I tested a simple way to price a match at half-time: turn the pre-match odds into each team's expected goals, assume the second half is the rest of the same match ({p(lv['share_second_half'], 0, False)} of goals come after half-time), and add the half-time score.</p>
<p>Teams do not play the second half the same way whatever the score. A team losing by two or more scored {p(se[-2]['ratio'] - 1, 0)} more second-half goals than expected; a team winning by two or more scored {p(1 - se[2]['ratio'], 0, False)} fewer. The trailing team attacks and the leading team defends.</p>
<img src="images/score_effects.png" alt="Second-half goals versus expected by half-time situation">
<p>So the simple model overrates leads. When a narrow pre-match favourite led by one goal at half-time, the model gave it a {p(lead['model_win'], 0, False)} chance of winning; it won {p(lead['actual_win'], 0, False)} of {lead['matches']:,} matches. From level at half-time, draws happened {p(lvl['actual_draw'], 0, False)} of the time against {p(lvl['model_draw'], 0, False)} predicted. Adding the score effect, estimated on seasons before 2010, improved the half-time forecasts on the {lv['test_matches']:,} later matches (log loss gain {g[0]:.4f}, 95% interval {g[1]:.4f} to {g[2]:.4f}).</p>
<p>The data have no in-play odds, so this shows what a naive in-play price would get wrong, not whether bookmakers make the same mistake.</p></div>""")
    return "".join(html)


def build(R: dict) -> str:
    f = facts(R)
    extra = more_findings(R, 6 if R["closing"] else 5)
    sc = R["model"]["scores"]
    names = {"uniform": "Equal chances (⅓ each)", "model": "Model from past scores", "market": "Betting market",
             "market_recalibrated": "Market, recalibrated", "market_plus_model": "Market + model combined"}
    rows = "".join(f"<tr><td>{names[k]}</td><td class=num>{v['log_loss']:.4f}</td><td class=num>{v['rps']:.4f}</td></tr>"
                   for k, v in sc.items())
    closing = ""
    if R["closing"]:
        closing = f"""
<div class=finding><div class=n>FINDING 4</div>
<h3>Late price moves point the right way</h3>
<p>Pinnacle publishes an opening price and a closing price just before kick-off. Over {f['cl_matches']} matches ({f['cl_years']}) the closing odds were the better forecast (log loss {f['ll_close']} against {f['ll_open']}). When an outcome's probability rose by at least 3 percentage points before kick-off, a bet at the <i>opening</i> odds returned {f['short_ret']} (95% interval {f['short_lo']} to {f['short_hi']}, {f['short_n']} bets). When it fell by 3 points, the return was {f['drift_ret']}.</p>
<img src="images/line_moves.png" alt="Return at opening odds after the price moved">
<p>Nobody knows the move in advance, so this is not a strategy. It shows that new information (team news, injuries, informed money) arrives before kick-off and that the opening price has not absorbed it yet. Several thresholds were tested, so the 3-point result should be read alongside the others: every “shortened” estimate is positive and every “drifted” one is negative.</p></div>"""
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Football Betting Market Efficiency</title>
<meta name=description content="A test of whether bookmakers' odds are accurate forecasts, using {f['matches']} English league matches.">
<link rel=preconnect href=https://fonts.googleapis.com><link rel=preconnect href=https://fonts.gstatic.com crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700&family=Instrument+Sans:wght@400;500;600&family=JetBrains+Mono:wght@500;600&display=swap" rel=stylesheet>
<style>{CSS}</style></head><body>
<header class=hero><div class=wrap>
<div class=kicker>Data science project · Python</div>
<h1>Testing the Efficiency of Football Betting Odds</h1>
<p class=lede>Bookmakers set odds on every professional football match. Odds can be read as probabilities, so they are a forecast. This project tests that forecast on {f['matches']} English {f['leagues']} matches from {f['years']}. If the market is efficient, outcomes happen as often as the odds say, and no simple rule makes money.</p>
<div class=result><b>Main result</b>The odds are close to calibrated, and a statistical model built from past scores could not improve on them. The market has two consistent weaknesses: long shots are overpriced, and the opening price lags behind news that arrives before kick-off. Neither weakness has faded over 20 years.</div>
<p class=note><code>Odds</code> Decimal odds of 2.50 return £2.50 for every £1 staked, including the stake. They imply a probability of 1 ÷ 2.50 = 40%. The three probabilities for a match (home win, draw, away win) add up to slightly more than 100%. The excess is the bookmaker's <i>margin</i>, its built-in profit.</p>
</div></header>
<main class=wrap>
<div class=stats>
<div class=stat><div class=v>{f['matches']}</div><div class=l>matches</div></div>
<div class=stat><div class=v>{f['n_seasons']}</div><div class=l>seasons</div></div>
<div class=stat><div class=v>{f['slope']}</div><div class=l>calibration slope (1 = perfect)</div></div>
<div class=stat><div class=v>{f['vb_avg']}</div><div class=l>return from model's “value” bets</div></div>
</div>

<h2>The questions</h2>
<ul>
<li><b>Calibration.</b> Do outcomes priced at 30% happen 30% of the time?</li>
<li><b>Bias.</b> Does betting on some kinds of outcome lose less than others?</li>
<li><b>Information.</b> Do prices that move before kick-off move the right way?</li>
<li><b>Forecasting.</b> Can a model built only from past scores beat the market, or add to it?</li>
<li><b>Sharp vs retail.</b> Can the price of a low-margin bookmaker find mistakes at the others?</li>
<li><b>In-play.</b> After half-time, do teams keep scoring at the rate the pre-match odds implied?</li>
<li><b>Change.</b> Has the market become more accurate over 20 years, and is the second division easier to beat?</li>
</ul>

<h2>What I found</h2>
<div class=finding><div class=n>FINDING 1</div>
<h3>The odds are close to calibrated</h3>
<p>Each point groups about 4,000 outcomes with similar prices. Outcomes priced at {f['top_priced']} happened {f['top_happened']} of the time. Outcomes priced at {f['low_priced']} happened {f['low_happened']} of the time. The calibration slope is {f['slope']} (95% interval {f['slope_lo']}–{f['slope_hi']}). A slope above 1 means favourites win slightly more often than priced and long shots slightly less.</p>
<img src="images/calibration.png" alt="Calibration of betting odds"></div>

<div class=finding><div class=n>FINDING 2</div>
<h3>Long shots are overpriced</h3>
<p>Betting £1 on every heavy favourite (odds 1–1.5) at the average bookmaker's price lost {f['fav_ret']}. Betting on every long shot (odds {f['long_band']}) lost {f['long_ret']}. This is the favourite–long-shot bias. It is explained by how bookmakers load their margin: if the margin is assumed to sit mostly on long shots (the “power” method), the calibration slope falls from {f['prop_slope']} to {f['power_slope']}.</p>
<img src="images/longshot.png" alt="Return by odds band">
<p>At the best price across about ten bookmakers, favourites roughly break even. That needs accounts at every bookmaker, and the best price is sometimes a mistake that would be cancelled or limited.</p></div>

<div class=finding><div class=n>FINDING 3</div>
<h3>Margins have fallen by more than half</h3>
<p>The average bookmaker's margin fell from {f['margin_first']} in {R['seasons'][0][:4]} to {f['margin_last']} by {R['seasons'][1][-4:]}. Pinnacle, which takes large bets and profits from volume, charges about {f['pin_margin']}.</p>
<img src="images/margins.png" alt="Bookmaker margin by season"></div>
{closing}
<div class=finding><div class=n>FINDING {5 if R['closing'] else 4}</div>
<h3>A model from past scores cannot beat the market</h3>
<p>The model gives each team an attack and a defence rating, fitted to past goals (a Poisson model, as in Dixon &amp; Coles, 1997). It is refitted every week using only earlier matches, and its one setting (how fast old results fade, {f['half_life']} days) was chosen on seasons before 2008 and never adjusted on the test seasons.</p>
<table><tr><th>Forecast ({f['eval_matches']} matches from {f['eval_from']})</th><th class=num>Log loss</th><th class=num>RPS</th></tr>{rows}</table>
<p>Lower is better for both scores. The model is far better than guessing but clearly worse than the market. Combining the two changed log loss by {f['gain']} (95% interval {f['gain_lo']} to {f['gain_hi']}), so the model adds nothing the odds do not already contain.</p>
<img src="images/value_bets.png" alt="Cumulative profit from the model's value bets">
<p>Betting whenever the model rated an outcome at least 5% more likely than the odds did, lost {f['vb_avg'].lstrip('-')} per bet at average odds and {f['vb_pin'].lstrip('-')} at Pinnacle. At the best price across all bookmakers it returned {f['vb_best']}, which is break-even within the uncertainty.</p></div>
{extra}

<h2>What I learned</h2>
<div class=cards>
<div class=card><h3>Score the probabilities</h3><p>Accuracy (“picked the winner”) hides most of the information. Log loss and the ranked probability score reward a forecast for being confident only when it should be.</p></div>
<div class=card><h3>Never let the future leak</h3><p>The model only sees matches before each week, the setting was tuned on separate early seasons, and a test checks this. Without these rules a backtest can look profitable by accident.</p></div>
<div class=card><h3>Report the uncertainty</h3><p>Betting returns are noisy. Every number here has a bootstrap interval that resamples whole matches, and several promising-looking strategies turned out to be inside the noise.</p></div>
</div>

<h2>How it's built</h2>
<ul>
<li><b>Data:</b> results and odds from up to ten bookmakers per match, from <a href="https://www.football-data.co.uk">football-data.co.uk</a>.</li>
<li><b>Margin removal:</b> three methods compared (proportional, power, Shin 1993).</li>
<li><b>Model:</b> weekly walk-forward Poisson ratings with time decay, in scikit-learn.</li>
<li><b>Combination:</b> multinomial logistic regression, refitted each season on earlier seasons only.</li>
<li><b>Tests:</b> nine pytest checks, including that the model never sees a match on or after the one it predicts.</li>
</ul>
<h2>Limits</h2>
<ul>
<li>English leagues only in the included data. <code>step2_download_more_data.py</code> adds Spain, Germany, Italy and France and the seasons since 2020.</li>
<li>The odds are snapshots collected by football-data.co.uk, not every price that was available.</li>
<li>This is a study of forecasting, not betting advice. The results show how hard the market is to beat.</li>
</ul>
</main>
<footer><div class=wrap>Code and data: <a href="{REPO_URL}">{REPO_URL.replace('https://', '')}</a></div></footer>
</body></html>"""


def main(out_dir: Path = ROOT / "output", docs: Path = ROOT / "docs"):
    R = json.loads((out_dir / "results.json").read_text())
    (docs / "images").mkdir(parents=True, exist_ok=True)
    for c in CHARTS:
        if (out_dir / f"{c}.png").exists():
            shutil.copy(out_dir / f"{c}.png", docs / "images" / f"{c}.png")
    (docs / "index.html").write_text(build(R))
    print(f"wrote {docs / 'index.html'}")


if __name__ == "__main__":
    main()
