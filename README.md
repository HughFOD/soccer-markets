# Soccer Odds Compared Across US Sportsbooks and Prediction Markets

Every match this week in six top leagues (Premier League, Championship, La
Liga, Bundesliga, Serie A, Ligue 1), priced by FanDuel, DraftKings, Fanatics,
BetMGM and Caesars, and by the prediction markets Kalshi and Polymarket. Each site's odds are compared with the
consensus of all of them, and any price clearly better than the consensus is
flagged.

**Website:** https://todayssoccerbets.com/

## How it works

1. **Collect the odds.** The Odds API supplies current odds from the major US
   sportsbooks and prediction markets. Kalshi and Polymarket charge a trading
   fee on every bet (rate x p x (1 - p) per $1 contract: 0.07 at Kalshi, 0.05
   at Polymarket US), so their prices are converted to what a bettor actually
   gets after the fee. Without this, prediction markets look like the best
   price far more often than they really are.
2. **Build the consensus.** Each site's odds are turned into chances with its
   cut removed, then averaged with equal weight. No site counts more than
   another. With the cuts removed, the consensus is the fair price.
3. **Flag the gaps.** A price more than 2% better than the consensus is
   flagged. Gaps over 25% are ignored as stale or mistyped prices.
4. **Rank the sites.** For each site: its cut, how often it has the best
   price, and how much it pays on average compared with the consensus.

American odds: +150 means a $100 bet wins $150; −200 means you bet $200 to win $100.

## Does beating the consensus mean anything?

A price that beats the consensus could be noise. The test is whether it still
looks good at kick-off, when every site has caught up with the news. Free
historical odds from American sportsbooks and prediction markets don't exist,
so the test uses the same method on 13 European bookmakers, 2019 to
2027 (16,328 matches), comparing each flagged price with the consensus
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

## Background research

Before building the comparison, I studied 52,841 matches from 2000 to 2026 to
see how accurate betting odds are: long shots are overpriced, prices that
move before kick-off move the right way, a model from past results can't beat
the odds, and teams behind at half-time score more than expected. The
details are on the [research page](https://todayssoccerbets.com/research.html).

## Running it

1. Get a free key at the-odds-api.com and save it as `odds_api_key.txt` in
   this folder (it is never uploaded).
2. Run `python3 update_everything.py`. It downloads the latest data, reruns
   the analysis and rebuilds the website. A refresh uses 12 of the free
   plan's 500 monthly credits.

## Layout

```
markets/usbooks.py     odds from The Odds API; consensus, flags, site rankings
markets/site.py        the homepage
markets/consensus.py   the consensus method and its historical test
markets/weekly.py      runs the weekly update
markets/report.py      the background research (charts, results.json)
markets/website.py     the research page; markets/readme.py writes this README
tests/                 automated checks
```

This is a study of pricing, not betting advice. Data: The Odds API and
[football-data.co.uk](https://www.football-data.co.uk).
