# Testing the Efficiency of Football Betting Odds

Bookmakers set odds on every professional football match. Odds can be read as
probabilities, so they are a forecast. This project tests that forecast on
16,670 English Premier League and Championship matches from 2000 to 2020.

If the market is efficient, outcomes happen as often as the odds say, and no
simple rule makes money after the bookmaker's margin.

**Main result.** The odds are close to calibrated, and a statistical model
built from past scores could not improve on them. The market has two
consistent weaknesses: long shots are overpriced, and the opening price lags
behind news that arrives before kick-off.

Website: https://hughfod.github.io/soccer-markets/

> **Odds, briefly.** Decimal odds of 2.50 return £2.50 for every £1 staked,
> including the stake, and imply a probability of 1 ÷ 2.50 = 40%. The three
> probabilities for a match (home, draw, away) add up to slightly more than
> 100%. The excess is the bookmaker's margin.

## Findings

**1. The odds are close to calibrated.** Outcomes priced at 64% happened 67%
of the time; outcomes priced at 13% happened 12%. The calibration slope is
1.10 (95% interval 1.06–1.14), where 1 is perfect. A slope above 1 means
favourites win slightly more often than priced.

![Calibration](docs/images/calibration.png)

**2. Long shots are overpriced.** At the average bookmaker's price, betting on
every heavy favourite (odds 1–1.5) lost 2.0% per bet; betting on every long
shot (odds 10+) lost 22%. This favourite–long-shot bias is explained by how
the margin is loaded: assuming the margin sits mostly on long shots (the power
method) brings the calibration slope from 1.10 to 1.01.

![Long shots](docs/images/longshot.png)

**3. Margins have fallen by more than half,** from 13.0% in 2000/01 to 5.2%
in 2019/20. Pinnacle charges about 2.4%.

![Margins](docs/images/margins.png)

**4. Late price moves point the right way.** On 4,658 matches with Pinnacle
opening and closing odds (2015–2020), the closing odds were the better
forecast. When an outcome's probability rose by 3+ points before kick-off, a
bet at the opening odds returned +11.2% (95% interval +2.5% to +20.7%); when
it fell by 3+ points, −18.9%. This is not a strategy (the move is not known in
advance), but it shows that the opening price has not yet absorbed team news
and informed money.

![Line moves](docs/images/line_moves.png)

**5. A model from past scores cannot beat the market.** A Poisson
attack/defence model (Dixon & Coles, 1997), refitted every week on earlier
matches only, scored log loss 1.039 against the market's 1.008 on 9,320 test
matches. Combining the two did not help (change +0.0002, interval −0.0004 to
+0.0009). Betting the model's "value" picks lost 6.7% per bet at average odds
and 3.6% at Pinnacle.

![Value bets](docs/images/value_bets.png)

| Forecast (9,320 matches, 2010–2020) | Log loss | RPS |
|---|---|---|
| Equal chances (⅓ each) | 1.0986 | 0.2339 |
| Model from past scores | 1.0390 | 0.2122 |
| Betting market | 1.0083 | 0.2057 |
| Market + model combined | 1.0087 | 0.2057 |

Full tables, with intervals for every number: `output/report.md` after a run.

## Method notes

- **No look-ahead.** The model predicts each week from matches strictly before
  it. Its one setting (how fast old results fade) was chosen on seasons before
  2008 and never tuned on the test seasons. A test checks both.
- **Honest uncertainty.** Every return and calibration figure has a bootstrap
  95% interval that resamples whole matches, since a match's three outcomes
  are linked.
- **Three margin-removal methods** (proportional, power, Shin 1993) are
  compared rather than assuming one.
- **Several thresholds** are reported for the line-move test, so one lucky
  cut-off cannot carry the result.

## Limits

- The included data are English leagues to 2020. `step2_download_more_data.py`
  adds Spain, Germany, Italy and France and every season since, including
  2020/21, when matches were played without crowds (the analysis of home
  advantage without crowds runs automatically once that season is present).
- Odds are snapshots collected by football-data.co.uk, not every available price.
- "Best odds" across ten bookmakers is an upper bound: it needs an account at
  each, and the best price is sometimes a mistake that would be cancelled.
- This is a study of forecasting, not betting advice.

## Running it

In PyCharm, open each file and click the green ▶ next to `if __name__ == "__main__":`

| File | What it does |
|---|---|
| `step1_setup.py` | creates `.venv` and installs everything (once) |
| `step2_download_more_data.py` | optional: more leagues and seasons from football-data.co.uk |
| `step3_run_analysis.py` | runs everything (about a minute); results in `output/` |
| `step4_run_tests.py` | tests: margin maths, calibration, no look-ahead |
| `step5_build_website.py` | rebuilds `docs/index.html` |

From a terminal: `pip install -r requirements.txt && python run.py && python -m pytest`

## Layout

```
markets/data.py        load football-data.co.uk files into one table; downloader
markets/margin.py      odds to probabilities: proportional, power, Shin
markets/efficiency.py  scores, calibration, returns, line moves, bootstrap intervals
markets/model.py       walk-forward Poisson ratings model
markets/report.py      runs every analysis; charts, results.json, report.md
markets/website.py     builds the website from results.json
tests/                 six checks
data/raw/              match files (football-data.co.uk)
```

Data: [football-data.co.uk](https://www.football-data.co.uk). The included
files come from the public mirror at github.com/jokecamp/FootballData.
