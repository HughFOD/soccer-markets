# Today's Soccer Bets

**Live site: [todayssoccerbets.com](https://todayssoccerbets.com/)**

A website that compares soccer odds across five US sportsbooks (FanDuel, DraftKings, Fanatics, BetMGM,
Caesars) and two prediction markets (Kalshi, Polymarket), works out a fair chance for every result, and
lists the bets that pay more than they should. It updates itself every morning, and every bet it lists is
saved and settled from the final score, so its record can't be edited after the fact.

Built in Python by Hugh O'Donnell, MS Data Science student at Stevens Institute of Technology
([LinkedIn](https://www.linkedin.com/in/hughfodonnell/)).

## Key findings

From 52,841 matches, 2000 to 2026 (full write-up on the [research page](https://todayssoccerbets.com/research.html)):

- **The odds are accurate, but slightly off in one consistent way.** Favorites win a little more often than
  their odds say, long shots a little less.
- **Long shots are the worst bet.** $100 on every heavy favorite (−200 or shorter) lost about $1 on average; on every long shot
  (+900 or longer), $27.
- **When odds move before kick-off, they're usually right.** An early bet on a team whose chance then rose 5+
  points made +$16 per $100; one whose chance fell 5+ points lost $18.
- **The site's method holds up.** Prices flagged as 2%+ better than the consensus were still better at
  kick-off 73% of the time (16,328 matches).
- **A model built from past scores can't beat the odds**, and teams behind at half-time score more in the
  second half than the odds expect.

Every bet the site lists is tracked on the [results page](https://todayssoccerbets.com/results.html), with
95% ranges so small samples aren't over-read.

## How it works

1. **Collect the odds.** The Odds API supplies current odds from the US sportsbooks and prediction markets.
   Kalshi and Polymarket charge a trading fee (rate x p x (1 - p) per $1 contract: 0.07 at Kalshi, 0.05 at
   Polymarket US), so their prices are converted to what a bettor actually gets after the fee.
2. **Build the consensus.** Each site's odds are turned into chances with its cut removed, then averaged with
   equal weight. With the cuts removed, the consensus is the fair price.
3. **Flag the gaps.** A price more than 2% better than the consensus is listed. Heavy favorites (−600 or
   shorter) need a bigger edge (+$3 per $100), and gaps over 25% are ignored as stale or mistyped prices.
4. **Keep score.** Each listed bet is saved at the price shown, re-checked each morning until kick-off, and
   settled from the final score.

American odds: +150 means a $100 bet wins $150; −200 means you bet $200 to win $100.

## Does beating the consensus mean anything?

A price that beats the consensus could be noise. The test is whether it still
looks good at kick-off, when every site has caught up with the news. Free
historical odds from American sportsbooks and prediction markets don't exist,
so the test uses the same method on 13 European bookmakers, 2019 to
2026 (16,328 matches), comparing each flagged price with the consensus
closing price.

| When a price beat the consensus by | Prices | Gap when flagged | Gap at kick-off | Still better at kick-off |
|---|---|---|---|---|
| More than 0% better | 2,058 | +0.9% | +0.8% | 57% |
| More than 1% better | 611 | +2.2% | +1.6% | 61% |
| More than 2% better | 205 | +3.7% | +4.0% | 73% |
| More than 3% better | 92 | +5.2% | +5.4% | 77% |
| More than 5% better | 26 | +8.7% | +7.3% | 77% |

Prices more than 2% better than the consensus were still better at kick-off
73% of the time, by 4.0% on average (95% range 2.8% to 5.2%).
Small gaps (under 1%) are mostly noise.

## Tech

- **Python:** pandas and NumPy for the data, SciPy and scikit-learn for the models and tests.
- **Statistics:** margin removal, calibration curves, bootstrap 95% ranges, a walk-forward Poisson team-rating
  model (Dixon and Coles), log-loss comparisons.
- **Automation:** a GitHub Actions job downloads the odds every morning, rebuilds the pages and commits them.
- **Website:** static HTML and CSS generated from Python, hosted on GitHub Pages, with a light and dark theme
  and a phone layout.
- **Tests:** pytest checks the maths, the settling of bets, and that the model never sees future matches.

## Running it

1. Get a key at the-odds-api.com and save it as `odds_api_key.txt` in this folder (it is never uploaded).
2. Run `python3 update_everything.py`. It downloads the latest data, reruns the analysis and rebuilds the
   website.

## Layout

```
markets/usbooks.py     odds from The Odds API; consensus, flags, site rankings
markets/extras.py      corners, cards and other bets on match days
markets/site.py        the homepage
markets/track.py       the track record: saves, re-checks and settles every listed bet
markets/consensus.py   the consensus method and its historical test
markets/model.py       the Poisson team-rating model
markets/report.py      the background research (charts, results.json)
markets/website.py     the research page; markets/readme.py writes this README
markets/weekly.py      runs the daily update
tests/                 automated checks
```

This is a study of pricing, not betting advice. Data: The Odds API and
[football-data.co.uk](https://www.football-data.co.uk).
