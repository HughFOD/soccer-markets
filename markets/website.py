"""Build docs/index.html (the GitHub Pages site) from output/results.json.

Run: python -m markets.website
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_URL = "https://github.com/HughFOD/soccer-markets"
CHARTS = ("bet_types", "fair_clv", "fair_weights", "fair_by_season", "calibration", "longshot", "margins", "line_moves", "value_bets", "soft_vs_sharp", "slope_by_season", "score_effects", "score_effect_checks")


LG = {"E0": "English Premier League", "E1": "English Championship", "SP1": "La Liga", "D1": "Bundesliga",
      "I1": "Serie A", "F1": "Ligue 1", "N1": "Eredivisie", "P1": "Primeira Liga"}


def _join(xs):
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


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
        "leagues": _join([LG.get(x, x) for x in R["leagues"]]),
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


def pence(x) -> str:
    """-0.02 -> '2p' (profit or loss per £1, as a positive number)."""
    return f"{abs(100 * x):.0f}p"


def more_findings(R: dict, start: int) -> str:
    """Findings from markets/sharp.py and markets/live.py."""
    html, n = [], start
    sh, sb = R.get("sharp"), R.get("soft_bets")
    if sh and sb:
        rules = {r["edge"]: r for r in sb["rules"]}
        r0, r2 = rules[0.0], rules[0.02]
        html.append(f"""
<div class=finding><div class=n>FINDING {n}</div>
<h3>Pinnacle's prices hint at bargains elsewhere, but the evidence is weak</h3>
<p>Once the margin is removed, Pinnacle and the average bookmaker are equally accurate. But bookmakers don't all update their prices at the same moment, so sometimes one offers better odds than Pinnacle's prices say are fair.</p>
<p>Betting only on those made {p(r0['return'])} per bet over {r0['bets']:,} bets (95% range {p(r0['lo'])} to {p(r0['hi'])}). When the gap was at least 2%, it made {p(r2['return'])} ({p(r2['lo'])} to {p(r2['hi'])}).</p>
<img src="images/soft_vs_sharp.png" alt="Return from bookmaker prices that beat Pinnacle's fair price">
<p>Every result is positive and roughly matches what Pinnacle's prices predicted. But the range always includes zero, most of the profit came in 2012–2014, and bookmakers restrict customers who bet this way.</p></div>""")
        n += 1
    bs = R.get("by_season")
    if bs:
        t = bs["table"]
        over = sum(r["longshot_return"] < r["fav_return"] for r in t)
        html.append(f"""
<div class=finding><div class=n>FINDING {n}</div>
<h3>Margins fell, but the long-shot bias didn't</h3>
<p>Season by season, there's no sign the odds have become more accurate. Long shots were the worse bet in {over} of {len(t)} seasons. Cheaper betting didn't mean better prices.</p>
<img src="images/slope_by_season.png" alt="Calibration slope by season"></div>""")
        n += 1
    bl = {r["league"]: r for r in R.get("by_league", [])}
    if {"E0", "E1"} <= set(bl):
        e0, e1 = bl["E0"], bl["E1"]
        html.append(f"""
<div class=finding><div class=n>FINDING {n}</div>
<h3>The second division isn't easier to beat</h3>
<p>Fewer people follow the Championship and less money is bet on it, so it could be priced less accurately than the Premier League. It isn't. Its odds are just as accurate, and my model didn't help in either league.</p>
<table><tr><th>League</th><th class=num>Matches</th><th class=num>Margin</th><th class=num>Calibration slope</th><th class=num>Loss betting on everything</th></tr>
<tr><td>Premier League</td><td class=num>{e0['matches']:,}</td><td class=num>{p(e0['margin'], 1, False)}</td><td class=num>{e0['slope']:.2f}</td><td class=num>{pence(e0['bet_everything'])} per £1</td></tr>
<tr><td>Championship</td><td class=num>{e1['matches']:,}</td><td class=num>{p(e1['margin'], 1, False)}</td><td class=num>{e1['slope']:.2f}</td><td class=num>{pence(e1['bet_everything'])} per £1</td></tr></table></div>""")
        n += 1
    lv = R.get("live")
    if lv:
        se = {r["margin"]: r for r in lv["score_effects"]}
        st = {(r["favourite"], r["half_time"]): r for r in lv["by_state"]}
        lead = st[("narrow favourite", "leading by 1")]
        lvl = st[("narrow favourite", "level")]
        rb = {r["check"]: r for r in lv.get("robustness", [])}
        allr = rb.get("All matches with a lead at half-time")
        checks = ""
        if allr:
            checks = f"""
<p><b>Is it really the scoreline?</b> Maybe games with early goals are just more open, and both teams score more. To rule that out, I compared the two teams in the same match. That cancels out anything that affects both sides, like an open game, the weather or the referee. The team that was behind was expected to score {p(allr['expected_share'], 1, False)} of the second-half goals. It actually scored {p(allr['actual_share'], 1, False)}.</p>
<img src="images/score_effect_checks.png" alt="The same test under twelve different checks">
<p>The pattern holds in all {len(rb)} checks: with or without red cards, in both decades, in both leagues, and after quiet or busy first halves. It's stronger when the lead is bigger, and stronger when the away team is the one chasing the game. If anything, the test is stacked against the finding. A team losing at half-time is probably weaker than its odds suggested, so you'd expect it to score less, not more.</p>"""
        html.append(f"""
<div class=finding><div class=n>FINDING {n}</div>
<h3>After half-time, the team that's behind scores more than expected</h3>
<p>The data includes half-time scores, so I tested the simplest way to price a match at half-time. Work out each team's expected goals from the pre-match odds, assume they keep scoring at that rate in the second half, and add the result to the half-time score.</p>
<p>That assumption is wrong. Teams losing by two or more goals scored {p(se[-2]['ratio'] - 1, 0, False)} more in the second half than expected. Teams winning by two or more scored {p(1 - se[2]['ratio'], 0, False)} fewer. Teams that are behind push forward, and teams that are ahead sit back.</p>
<img src="images/score_effects.png" alt="Second-half goals compared with expected, by half-time score">{checks}
<p>This means the simple model overrates the team in front. A slight favourite leading 1–0 at half-time was given a {p(lead['model_win'], 0, False)} chance of winning, and won {p(lead['actual_win'], 0, False)} of the time over {lead['matches']:,} matches. Games level at half-time ended in a draw {p(lvl['actual_draw'], 0, False)} of the time, not the {p(lvl['model_draw'], 0, False)} predicted. Adjusting for the scoreline, using only seasons before 2010, made the half-time predictions measurably better for the {lv['test_matches']:,} matches after that.</p>
<p>The data doesn't include live odds, so this shows where a simple live price goes wrong, not whether bookmakers make the same mistake.</p></div>""")
    return "".join(html)


ODDS_LONG = "Long shot (over 4.00, +300 or longer)"


def engine_section(R: dict) -> tuple[str, dict]:
    fr = R.get("fair")
    if not fr:
        return "", {}
    bt = fr["backtest"]
    rules = {r["threshold"]: r for r in bt["rules"]}
    r2 = rules[0.02]
    acc = {r["source"]: r for r in fr["accuracy"]}
    seasons = [r["season"] for r in bt["by_season"]]
    yrs = f"{seasons[0][:4]} to {seasons[-1][-4:]}" if seasons else ""
    w = fr["latest_weights"]
    from .report import BOOK_NAMES as names
    top = sorted(w.items(), key=lambda kv: -kv[1])
    tot = sum(w.values())
    rows = "".join(f"<tr><td>More than {100 * r['threshold']:.0f}% better</td><td class=num>{r['bets']:,}</td>"
                   f"<td class=num>{p(r['expected'])}</td><td class=num>{p(r['clv'])}</td><td class=num>{100 * r['beat_close']:.0f}%</td></tr>"
                   for r in bt["rules"])
    bs = bt["by_season"]
    early = [r for r in bs if r["season"] < "2019"]
    late = [r for r in bs if r["season"] >= "2019"]
    def pooled(rows):
        n = sum(r["bets"] for r in rows)
        return n, (sum(r["bets"] * r["clv"] for r in rows) / n if n else float("nan"))
    ne, ce = pooled(early)
    nl, cl_ = pooled(late)
    if late:
        worst = min(late, key=lambda r: r["clv"])
        recent = (f"Up to 2018/19 the engine flagged about {ne / max(len(early), 1):.0f} prices a season. Since then, as bookmakers have "
                  f"copied the sharpest prices faster, it has flagged about {nl / max(len(late), 1):.0f} a season. Those that remain still beat "
                  f"the closing price by {p(cl_, 1, False)} on average. Single seasons are noisy with so few flags (the weakest, "
                  f"{worst['season'][:4]}/{worst['season'][-2:]}, was {p(worst['clv'], 1, False)}), but the edge has held up in every one. "
                  f"On today's prices this is a tool for spotting the occasional mistake, not a steady stream of them.")
    else:
        recent = ""
    k = dict(recent=recent, n=bt["matches"], weeks=bt["weeks"], yrs=yrs, beat=f"{100 * r2['beat_close']:.0f}%", clv=p(r2["clv"]),
             clv_lo=p(r2["clv_lo"]), clv_hi=p(r2["clv_hi"]), exp=p(r2["expected"]), per_week=f"{r2['bets_per_week']:.1f}",
             ret=p(r2["return"]), ret_lo=p(r2["lo"]), ret_hi=p(r2["hi"]), bets=r2["bets"])
    html = f"""
<h2>How it works</h2>
<div class=cards>
<div class=card><h3>1. Remove each bookmaker's cut</h3><p>Every bookmaker's odds are turned into fair chances, taking more of the margin off long shots, where bookmakers put most of it.</p></div>
<div class=card><h3>2. Blend the bookmakers</h3><p>The chances are combined into one fair price. Each bookmaker's weight is learned from how well its prices predicted Pinnacle's closing price, the sharpest in the data, over the previous two seasons.</p></div>
<div class=card><h3>3. Flag out-of-line prices</h3><p>Any regular bookmaker offering odds more than 2% better than the fair price is flagged, along with how big the gap is.</p></div>
</div>
<p style="color:var(--ink2)">Why learn from closing prices and not results? Results are mostly luck, so learning from them needs decades of data and still jumps around. The closing price, set just before kick-off, is the market's final and best-informed view, so it is a much cleaner target. Today the blend is {', '.join(f"{names.get(b, b)} {100 * v / tot:.0f}%" for b, v in top[:3])}, with small weights for the rest.</p>
<p style="color:var(--ink2)">Betting exchanges such as Betfair are left out. In thin markets their prices swing a lot, and with them in, one exchange took most of the weight on its own. Leaving them out changed the results by less than a tenth of a point. The backtest runs to 2025/26, the last season the data includes Pinnacle's closing price.</p>
<div class=finding><img src="images/fair_weights.png" alt="Each bookmaker's share of the fair price"></div>

<h2>Track record</h2>
<p style="color:var(--ink2)">The test is whether flagged prices were really better than fair. Profit is a poor test because it depends on who won, so it takes thousands of bets to mean anything. The standard test is the <b>closing price</b>: if you regularly get better odds than the market's final price, your prices were genuinely good, whoever won.</p>
<div class=finding>
<h3>Flagged prices beat the closing price by almost exactly the predicted amount</h3>
<p>Across {k['n']:,} matches from {k['yrs']}, using weights learned only from earlier seasons, the engine flagged {k['bets']:,} prices as more than 2% better than fair. {k['beat']} of them beat the closing price. On average they beat it by {k['clv'].lstrip('+')} (95% range {k['clv_lo'].lstrip('+')} to {k['clv_hi'].lstrip('+')}), against the {k['exp'].lstrip('+')} the engine predicted. Higher thresholds flag fewer prices with bigger edges, and the prediction holds at every level.</p>
<img src="images/fair_clv.png" alt="Edge over the closing price for flagged prices">
<table><tr><th>Flag when the price is</th><th class=num>Prices</th><th class=num>Predicted edge</th><th class=num>Edge vs close</th><th class=num>Beat close</th></tr>{rows}</table>
<p>The fair price itself is also closer to the closing price than any single bookmaker, including Pinnacle's own earlier price ({100 * acc['Pinnacle alone']['vs_fair']:.0f}% further away) and Bet365 ({100 * acc['Bet365 alone']['vs_fair']:.0f}% further).</p>
<p><b>The edge has shrunk.</b> {k['recent']}</p>
<img src="images/fair_by_season.png" alt="Flags and edge over the closing price, season by season">
<p>The profit on the 2% flags was {k['ret']} per bet, but the 95% range ({k['ret_lo']} to {k['ret_hi']}) is wide, which is exactly why the closing price is the better test. Flags have also become rarer as bookmakers' prices have tightened, and in practice bookmakers limit customers who consistently beat their prices.</p>
</div>"""
    bt_types = fr.get("bet_types") or []
    if bt_types:
        T = {(r["group"], r["type"]): r for r in bt_types}
        price = [r for r in bt_types if r["group"] == "Price"]
        best = max(price, key=lambda r: r["lo"])  # the type whose profit is most clearly above zero
        lg = [r for r in bt_types if r["group"] == "League"]
        lg_best, lg_worst = max(lg, key=lambda r: r["clv"]), min(lg, key=lambda r: r["clv"])
        gaps = [r for r in bt_types if r["group"] == "Size of gap"]
        trows = "".join(f"<tr><td>{r['type'].split(' (')[0]}<br><small>{r['type'].split(' (')[1].rstrip(')') if ' (' in r['type'] else ''}</small></td><td class=num>{r['bets']:,}</td>"
                        f"<td class=num>{p(r['clv'])}</td><td class=num>{100 * r['beat_close']:.0f}%</td><td class=num>{p(r['return'])}<br><small>{p(r['lo'])} to {p(r['hi'])}</small></td></tr>" for r in price)
        html += f"""
<h2>The best types of bets</h2>
<p style="color:var(--ink2)">Not every flagged price is equally good. Splitting the {k['bets']:,} flagged prices by type shows where the edge is most reliable.</p>
<div class=finding>
<h3>{best['type'].split(' (')[0]}s are the most reliable</h3>
<p>Prices on {best['type'].split(' (')[0].lower()}s ({best['type'].split(' (')[1].rstrip(')')}) beat the closing price {100 * best['beat_close']:.0f}% of the time and returned {p(best['return'])} per bet (95% range {p(best['lo'])} to {p(best['hi'])}). Long shots have a similar average edge, but only {100 * T[('Price', ODDS_LONG)]['beat_close']:.0f}% beat the close and their profit swings widely, because a few results decide everything.</p>
<table><tr><th>Price</th><th class=num>Flags</th><th class=num>Edge vs close</th><th class=num>Beat close</th><th class=num>Return per bet</th></tr>{trows}</table>
<img src="images/bet_types.png" alt="Edge over the closing price by type of bet">
<ul>
<li><b>Bigger gaps are worth more.</b> Prices {gaps[0]['type'][4:]} better than fair beat the close by {p(gaps[0]['clv'], 1, False)}; gaps {gaps[-1]['type'][4:]} beat it by {p(gaps[-1]['clv'], 1, False)}.</li>
<li><b>League matters a little.</b> The edge is largest in the {lg_best['type']} ({p(lg_best['clv'], 1, False)}) and smallest in the {lg_worst['type']} ({p(lg_worst['clv'], 1, False)}).</li>
<li><b>Home, draw and away are similar.</b> Each beats the close by {p(min(T[('Result', x)]['clv'] for x in ('Home win', 'Draw', 'Away win')), 1, False)} to {p(max(T[('Result', x)]['clv'] for x in ('Home win', 'Draw', 'Away win')), 1, False)}.</li>
</ul></div>"""
    return html, k


def build(R: dict) -> str:
    f = facts(R)
    extra = more_findings(R, 6 if R["closing"] else 5)
    engine, k = engine_section(R)
    sc = R["model"]["scores"]
    names = {"uniform": "Equal chances (⅓ each)", "model": "My model", "market": "The odds",
             "market_recalibrated": "The odds, recalibrated", "market_plus_model": "The odds and my model combined"}
    rows = "".join(f"<tr><td>{names[k]}</td><td class=num>{v['log_loss']:.4f}</td><td class=num>{v['rps']:.4f}</td></tr>"
                   for k, v in sc.items())
    avg = R["longshot"]["average"]
    closing = ""
    if R["closing"]:
        closing = f"""
<div class=finding><div class=n>FINDING 4</div>
<h3>Prices that move before kick-off move the right way</h3>
<p>Pinnacle records an opening price and a closing price just before kick-off. Across {f['cl_matches']} matches from {f['cl_years']}, the closing price was the better prediction. When an outcome's chance rose by 3 percentage points or more before kick-off, a bet at the opening price made {f['short_ret']} per bet (95% range {f['short_lo']} to {f['short_hi']}). When its chance fell by 3 points, the same bet lost {f['drift_ret'].lstrip('-')}.</p>
<img src="images/line_moves.png" alt="Return at the opening price after the price moved">
<p>This isn't a strategy, because you can't know the move in advance. What it shows is that real information, such as team news and injuries, arrives before kick-off and the opening price hasn't caught up. I tried several cut-offs, not just 3 points, and they all point the same way.</p></div>"""
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>A Fair-Price Engine for Football Odds</title>
<meta name=description content="Combines about ten bookmakers into one fair price for every upcoming football match, and flags prices that are better than fair.">
<link rel=preconnect href=https://fonts.googleapis.com><link rel=preconnect href=https://fonts.gstatic.com crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700&family=Instrument+Sans:wght@400;500;600&family=JetBrains+Mono:wght@500;600&display=swap" rel=stylesheet>
<style>{CSS}.cta{{display:inline-block;margin-top:22px;background:#eb6834;color:#fff;font-weight:600;padding:10px 18px;border-radius:8px;text-decoration:none}}</style></head><body>
<header class=hero><div class=wrap>
<div class=kicker>Data science project · Python</div>
<h1>A Fair-Price Engine for Football Odds</h1>
<p class=lede>Bookmakers often disagree about the same match. This tool combines them into one fair price for every upcoming game, then flags any American sportsbook (DraftKings, FanDuel, BetMGM, Caesars and others) whose odds are better than fair. It is built the way a market maker thinks: work out what something is really worth, then look for prices that are out of line.</p>
<div class=result><b>Main result</b>When the engine flagged a price as more than 2% better than fair, that price beat the market's closing price {k.get('beat', '')} of the time, by {k.get('clv', '').lstrip('+')} on average. That is almost exactly the {k.get('exp', '').lstrip('+')} the engine predicted, tested on {k.get('n', 0):,} matches it had never seen.</div>
<a class=cta href="this-week.html">See this week's prices at American sportsbooks →</a>
<p class=note><code>How odds work</code> American odds of +150 mean a $100 bet wins $150; −200 means you bet $200 to win $100. +150 implies a 40% chance. Add up the chances for a home win, a draw and an away win and you get a little over 100%. The extra is the bookmaker's cut, called the <i>margin</i>. The track record below is from European bookmakers, because free historical odds from American sportsbooks don't exist.</p>
</div></header>
<main class=wrap>
<div class=stats>
<div class=stat><div class=v>{k.get('n', 0):,}</div><div class=l>matches in the backtest</div></div>
<div class=stat><div class=v>{k.get('beat', '')}</div><div class=l>of flagged prices beat the closing price</div></div>
<div class=stat><div class=v>{k.get('clv', '')}</div><div class=l>average edge over the closing price</div></div>
<div class=stat><div class=v>{k.get('bets', 0):,}</div><div class=l>prices flagged in the backtest</div></div>
</div>
{engine}

<h2>What {f['n_seasons']} seasons of odds show</h2>
<p style="color:var(--ink2)">Before building the engine, I studied how accurate the odds are, using {f['matches']} matches from the {f['leagues']} between {f['years'].replace(' to ', ' and ')}. These findings explain why the engine is designed the way it is.</p>

<div class=finding><div class=n>FINDING 1</div>
<h3>The odds are accurate</h3>
<p>I grouped every outcome by the chance the odds gave it, then checked how often it happened. Outcomes given a {f['top_priced']} chance happened {f['top_happened']} of the time. Outcomes given a {f['low_priced']} chance happened {f['low_happened']} of the time. Perfect predictions would sit on the diagonal line, and these are close. They're slightly too steep: favourites win a little more often than the odds say, and long shots a little less.</p>
<img src="images/calibration.png" alt="How often outcomes happened, against the chance the odds gave them"></div>

<div class=finding><div class=n>FINDING 2</div>
<h3>Long shots are a bad bet</h3>
<p>Betting £1 on every heavy favourite (odds below 1.5) at the average bookmaker's price lost {pence(avg[0]['return'])} per bet. Betting £1 on every long shot (odds of 10 or more) lost {pence(avg[-1]['return'])}. This is the favourite–long-shot bias, which also shows up in horse racing and other betting markets.</p>
<p>It comes from how bookmakers spread their margin: they put more of it on long shots. Removing the margin that way makes the odds almost perfectly accurate (a slope of {f['power_slope']} instead of {f['prop_slope']}).</p>
<img src="images/longshot.png" alt="Profit or loss by odds">
<p>Taking the best price from about ten bookmakers gets favourites to roughly break even. In practice that needs an account with every bookmaker, and the very best price is sometimes a mistake that gets cancelled.</p></div>

<div class=finding><div class=n>FINDING 3</div>
<h3>Bookmakers take a smaller cut than they used to</h3>
<p>The average bookmaker's margin fell from {f['margin_first']} in {R['seasons'][0][:4]} to {f['margin_last']} by {R['seasons'][1][-4:]}. Pinnacle, which aims for high volume at low margins, takes about {f['pin_margin']}.</p>
<img src="images/margins.png" alt="Bookmaker margin by season"></div>
{closing}
<div class=finding><div class=n>FINDING {5 if R['closing'] else 4}</div>
<h3>A model built from past results can't beat the odds</h3>
<p>The model rates each team's attack and defence from its recent goals, a standard approach from Dixon and Coles (1997). Every week it is refitted using only matches already played, so it never sees the future. Its one setting, how quickly old results fade, was chosen using seasons before 2008 and then left alone.</p>
<table><tr><th>Prediction ({f['eval_matches']} matches from {f['eval_from']})</th><th class=num>Log loss</th><th class=num>RPS</th></tr>{rows}</table>
<p>Lower scores are better. The model is much better than guessing, but clearly worse than the odds, and adding it to the odds didn't help at all.</p>
<img src="images/value_bets.png" alt="Running profit from betting the model's picks">
<p>Betting on every outcome the model rated at least 5% more likely than the odds did lost {pence(float(f['vb_avg'].rstrip('%')) / 100)} per £1 at average prices and {pence(float(f['vb_pin'].rstrip('%')) / 100)} at Pinnacle. Even at the best available price, it only broke even.</p></div>
{extra}

<h2>What I learned</h2>
<div class=cards>
<div class=card><h3>Test against the closing price</h3><p>Results are mostly luck. Learning from and testing against the closing price makes the engine steady and its accuracy measurable.</p></div>
<div class=card><h3>Never let the model see the future</h3><p>The model only uses matches already played, its setting was chosen on separate early seasons, and a test checks both. Without that, a backtest can look profitable by accident.</p></div>
<div class=card><h3>Always show the uncertainty</h3><p>Betting returns are noisy. Every number here comes with a 95% range, and several strategies that looked promising turned out to be noise.</p></div>
</div>

<h2>How it's built</h2>
<ul>
<li><b>Data:</b> results and odds from up to ten bookmakers per match, from <a href="https://www.football-data.co.uk">football-data.co.uk</a>.</li>
<li><b>Removing the margin:</b> three methods compared (proportional, power and Shin's 1993 model).</li>
<li><b>Fair price:</b> a weighted logarithmic pool of bookmakers, with weights fitted to closing prices each season (SciPy).</li>
<li><b>Model:</b> team ratings refitted every week on past matches only, in scikit-learn.</li>
<li><b>Combining forecasts:</b> logistic regression, refitted each season on earlier seasons only.</li>
<li><b>Uncertainty:</b> 95% ranges from resampling whole matches (the bootstrap).</li>
<li><b>Tests:</b> sixteen automated checks, including one that the model never sees a match before predicting it.</li>
</ul>
<h2>Limits</h2>
<ul>
<li>The track record needs closing prices, which the included files have from 2015. Running <code>step2_download_more_data.py</code> extends it to the current season and four more leagues.</li>
{"<li>The included data covers English football only. <code>update_everything.py</code> adds Spain, Germany, Italy, France and the seasons since 2020.</li>" if set(R["leagues"]) <= {"E0", "E1"} else ""}
<li>The odds are snapshots collected by football-data.co.uk, not every price on offer.</li>
<li>This is a study of forecasting, not betting advice. Mostly, it shows how hard the market is to beat.</li>
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
