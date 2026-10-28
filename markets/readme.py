"""Write README.md from output/results.json, so its numbers always match the latest run.

Run: python -m markets.readme   (update_everything.py does this for you)
"""
from __future__ import annotations

import json
from pathlib import Path

from .website import LG, _join, p

ROOT = Path(__file__).resolve().parent.parent


def pence(x):
    return f"{abs(100 * x):.0f}p"


def build(R: dict) -> str:
    fr = R["fair"]
    bt = fr["backtest"]
    rules = {r["threshold"]: r for r in bt["rules"]}
    r2 = rules[0.02]
    seasons = [r["season"] for r in bt["by_season"]]
    yrs = f"{seasons[0][:4]}–{seasons[-1][-4:]}" if seasons else ""
    acc = {r["source"]: r for r in fr["accuracy"]}
    w = fr["latest_weights"]
    tot = sum(w.values())
    from .report import BOOK_NAMES as names
    blend = ", ".join(f"{names.get(b, b)} {100 * v / tot:.0f}%" for b, v in sorted(w.items(), key=lambda kv: -kv[1])[:4])
    leagues = _join([LG.get(x, x) for x in R["leagues"]])
    avg = R["longshot"]["average"]
    cl = R.get("closing")
    lv = R.get("live")
    mm = R["model"]
    from .website import engine_section
    recent = "**The edge has shrunk.** " + engine_section(R)[1].get("recent", "")
    rule_rows = "\n".join(
        f"| More than {100 * r['threshold']:.0f}% better | {r['bets']:,} | {p(r['expected'])} | "
        f"{p(r['clv'])} ({p(r['clv_lo'])} to {p(r['clv_hi'])}) | {100 * r['beat_close']:.0f}% |" for r in bt["rules"])
    acc_rows = "\n".join(f"| {r['source']} | {r['distance_to_close']:.5f} | {p(r['vs_fair'], 0)} |" for r in fr["accuracy"])

    L = [f"""# A Fair-Price Engine for Football Odds

Bookmakers often disagree about the same match. This tool combines about ten
of them into one fair price for every upcoming game, then flags any bookmaker
whose odds are better than fair. It is built the way a market maker thinks:
work out what something is really worth, then look for prices that are out of
line.

**Main result.** When the engine flagged a price as more than 2% better than
fair, that price beat the market's closing price {100 * r2['beat_close']:.0f}% of the time, by
{p(r2['clv'], 1, False)} on average (95% range {p(r2['clv_lo'], 1, False)} to {p(r2['clv_hi'], 1, False)}). That is almost exactly the
{p(r2['expected'], 1, False)} the engine predicted, tested on {bt['matches']:,} matches ({yrs}) it had never seen.

- Website: https://hughfod.github.io/soccer-markets/
- This week's prices: https://hughfod.github.io/soccer-markets/this-week.html

> **How odds work.** Odds of 2.50 pay £2.50 for every £1 bet, including your
> stake. That implies a 40% chance (1 ÷ 2.50). The chances for a home win, a
> draw and an away win add up to a little over 100%. The extra is the
> bookmaker's cut, called the margin.

## How it works

1. **Remove each bookmaker's cut.** Every bookmaker's odds are turned into
   fair chances, taking more of the margin off long shots, where bookmakers
   put most of it.
2. **Blend the bookmakers.** The chances are combined into one fair price (a
   weighted logarithmic pool). Each bookmaker's weight is learned from how well
   its prices predicted the sharpest closing price in the previous two seasons.
   Today the blend is {blend}.
3. **Flag out-of-line prices.** Any regular bookmaker offering odds more than
   2% better than the fair price is flagged.

In 2026/27 the data stopped including Pinnacle, so the engine now learns from
and is tested against the Betfair Exchange closing price, the sharpest price
left.

Why learn from closing prices and not results? Results are mostly luck, so
weights learned from them are noisy and unstable. The closing price, set just before kick-off, is the
market's final and best-informed view, so it is a much cleaner target.

![Weights](docs/images/fair_weights.png)

## Track record

Profit is a poor test of a price because it depends on who won. The standard
test is the closing price: if you regularly get better odds than the market's
final price, your prices were genuinely good, whoever won.

![Closing-line value](docs/images/fair_clv.png)

| Flag when the price is | Prices | Predicted edge | Edge vs closing price (95% range) | Beat close |
|---|---|---|---|---|
{rule_rows}

The fair price is also closer to the closing price than any single bookmaker:

| Price | Distance to closing price | vs this engine |
|---|---|---|
{acc_rows}

{recent}

![By season](docs/images/fair_by_season.png)

The profit on the 2% flags was {p(r2['return'])} per bet, but its 95% range
({p(r2['lo'])} to {p(r2['hi'])}) is wide, which is why the closing price is the better test.
In practice, bookmakers limit customers who consistently beat their prices.

## What {len(R['margins'])} seasons of odds show

Before building the engine, I studied how accurate the odds are, using
{R['matches']:,} matches from the {leagues}. These findings explain the design.

1. **The odds are accurate, but slightly too cautious.** Calibration slope
   {R['calibration']['pooled']['slope']:.2f} (1.00 is perfect): favourites win a little more often than
   the odds say. ![Calibration](docs/images/calibration.png)
2. **Long shots are a bad bet.** £1 on every heavy favourite lost
   {pence(avg[0]['return'])}; £1 on every long shot (odds of 10 or more) lost {pence(avg[-1]['return'])}. Bookmakers put more
   of their margin on long shots, which is why the engine removes it that way.
   ![Long shots](docs/images/longshot.png)
3. **Bookmakers take a smaller cut than they used to,** from
   {p(R['margins'][0]['avg_margin'], 1, False)} to {p(R['margins'][-1]['avg_margin'], 1, False)}. ![Margins](docs/images/margins.png)"""]
    if cl:
        mv = {(r["threshold"], r["direction"]): r for r in cl["moves"]}
        s3 = mv[(0.03, "shortened")]
        L.append(f"""4. **Prices that move before kick-off move the right way,** so the closing
   price knows more than the opening one. When a chance rose 3+ points before
   kick-off, a bet at the opening price made {p(s3['return'])}. This is why the engine is
   judged against the closing price. ![Line moves](docs/images/line_moves.png)""")
    L.append(f"""5. **A model built from past results can't beat the odds.** Team ratings
   refitted every week scored log loss {mm['scores']['model']['log_loss']:.3f} against the odds' {mm['scores']['market']['log_loss']:.3f}, and adding the
   model to the odds didn't help. The engine therefore starts from the odds,
   not from a model. ![Model](docs/images/value_bets.png)""")
    if lv:
        rb = {r["check"]: r for r in lv["robustness"]}
        a = rb["All matches with a lead at half-time"]
        L.append(f"""6. **After half-time, the team that's behind scores more than expected.**
   Within the same match, the trailing team scored {p(a['actual_share'], 1, False)} of second-half goals
   against {p(a['expected_share'], 1, False)} expected, and the pattern holds in all {len(rb)} checks. A
   simple live price that ignores this overrates the team in front.
   ![Score effects](docs/images/score_effect_checks.png)""")
    L.append("""
Full tables with 95% ranges for every number are in `output/report.md` after a run.

## Running it

In PyCharm, open `update_everything.py` and click the green ▶ next to
`if __name__ == "__main__":`. It sets up the first time, downloads the latest
odds, reruns everything, prices this week's matches and rebuilds the website
and this README. Run `step6_this_week.py` on its own to refresh just this
week's prices.

From a terminal: `pip install -r requirements.txt && python update_everything.py && python -m pytest`

## Layout

```
markets/fairprice.py   the engine: margin removal, weighted pool, weights from closing prices, flags, backtest
markets/weekly.py      prices this week's matches -> docs/this-week.html
markets/data.py        loads and downloads football-data.co.uk files
markets/margin.py      odds to fair chances: proportional, power, Shin
markets/efficiency.py  scores, calibration, returns, bootstrap ranges
markets/model.py       team-ratings model (the baseline the odds beat)
markets/sharp.py       Pinnacle vs other bookmakers, by season, by league
markets/live.py        half-time scores and score effects
markets/report.py      runs every analysis; charts, results.json, report.md
markets/website.py     builds the website; markets/readme.py builds this README
tests/                 fourteen checks, including that nothing is fitted on the matches it is tested on
```

## Limits

- The track record needs closing prices, which the data has from 2015/16.
- Odds are snapshots collected twice a week by football-data.co.uk, so a
  flagged price may already have moved.
- This is a study of pricing, not betting advice.

Data: [football-data.co.uk](https://www.football-data.co.uk).
""")
    return "\n".join(L)


def main(out_dir: Path = ROOT / "output"):
    R = json.loads((out_dir / "results.json").read_text())
    (ROOT / "README.md").write_text(build(R))
    print("wrote README.md")


if __name__ == "__main__":
    main()
