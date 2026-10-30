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
    cs = R.get("consensus")
    rr = {x["threshold"]: x for x in cs["rules"]} if cs else {}
    r2 = rr.get(0.02)
    hist = ""
    if cs:
        rows = "\n".join(f"| More than {100 * x['threshold']:.0f}% better | {x['bets']:,} | {p(x['expected'])} | {p(x['edge_vs_close'])} | {100 * x['beat_close']:.0f}% |"
                         for x in cs["rules"])
        hist = f"""## Does beating the consensus mean anything?

A price that beats the consensus could be noise. The test is whether it still
looks good at kick-off, when every site has caught up with the news. Free
historical odds from American sportsbooks and prediction markets don't exist,
so the test uses the same method on {len(cs['books'])} European bookmakers, {cs['seasons'][0][:4]} to
{cs['seasons'][-1][-4:]} ({cs['matches']:,} matches), comparing each flagged price with the consensus
closing price.

| When a price beat the consensus by | Prices | Gap when flagged | Gap at kick-off | Still better at kick-off |
|---|---|---|---|---|
{rows}

Prices more than 2% better than the consensus were still better at kick-off
{100 * r2['beat_close']:.0f}% of the time, by {p(r2['edge_vs_close'], 1, False)} on average (95% range {p(r2['lo'], 1, False)} to {p(r2['hi'], 1, False)}).
Small gaps (under 1%) are mostly noise.
"""
    return f"""# Soccer Odds Compared Across US Sportsbooks and Prediction Markets

Every match this week in six top leagues (Premier League, Championship, La
Liga, Bundesliga, Serie A, Ligue 1), priced by FanDuel, DraftKings, Fanatics,
BetMGM and Caesars, and by the prediction markets Kalshi and Polymarket.
(Caesars and Fanatics appear only on a paid Odds API plan.) Each site's odds are compared with the
consensus of all of them, and any price clearly better than the consensus is
flagged.

**Website:** https://todayssoccerbets.com/

## How it works

1. **Collect the odds.** The Odds API supplies current odds from the major US
   sportsbooks and prediction markets.
2. **Build the consensus.** Each site's odds are turned into chances with its
   cut removed, then averaged with equal weight. No site counts more than
   another. With the cuts removed, the consensus is the fair price.
3. **Flag the gaps.** A price more than 2% better than the consensus is
   flagged. Gaps over 25% are ignored as stale or mistyped prices.
4. **Rank the sites.** For each site: its cut, how often it has the best
   price, and how much it pays on average compared with the consensus.

American odds: +150 means a $100 bet wins $150; −200 means you bet $200 to win $100.

{hist}
## Background research

Before building the comparison, I studied {R['matches']:,} matches from 2000 to 2026 to
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
"""


def main(out_dir: Path = ROOT / "output"):
    R = json.loads((out_dir / "results.json").read_text())
    (ROOT / "README.md").write_text(build(R))
    print("wrote README.md")


if __name__ == "__main__":
    main()
