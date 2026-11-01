"""About page (docs/about.html): what the site does, how a bet is chosen, what's covered, how picks are
scored, responsible gambling and who made it.

Rebuild after changing sites or competitions:  python -m markets.about
"""
from __future__ import annotations

import html
from pathlib import Path

from . import theme
from .site import CSS
from .usbooks import SITES, SPORTS

ROOT = Path(__file__).resolve().parent.parent

PAGE_CSS = """
.about h2{margin-top:0}.about .section+.section{padding-top:0}
.facts{color:var(--ink2);padding-left:20px;max-width:760px;margin:0}.facts li{margin:8px 0}.facts b{color:var(--ink)}
.help{background:var(--bg2);border-radius:18px;padding:22px 24px;max-width:760px}
.help p{margin:0 0 8px}.help p:last-child{margin:0}
"""


def build() -> str:
    e = html.escape
    books = [n for n, k in SITES.values() if k == "Sportsbook"]
    markets = [n for n, k in SITES.values() if k != "Sportsbook"]
    leagues = list(SPORTS.values())
    return f"""<!doctype html><html lang=en><head>{theme.HEAD}
{theme.meta("about.html", "About · Today's Soccer Bets",
            "How Today's Soccer Bets chooses each bet, which sites and competitions it covers, and how its picks are scored.")}
<style>{CSS}{PAGE_CSS}</style></head><body class=about>
{theme.nav("about")}
<section class=hero><div class=wrap>
<p class=eyebrow>About</p>
<h1>About Today's Soccer Bets.</h1>
<p class=lede>A free daily list of soccer bets where one site's odds are better than all the sites together say they should be.</p>
</div></section>

<section class=section><div class=wrap>
<h2>How a bet is chosen.</h2>
<div class=cards>
<div class=card><h3>Collect the odds.</h3><p>Every site's odds for every bet, through The Odds API. Prediction-market prices are
converted to what you get after their trading fee (Kalshi 0.07 &times; p &times; (1&minus;p) per $1 contract,
Polymarket 0.05 &times; p &times; (1&minus;p)).</p></div>
<div class=card><h3>Work out what's expected.</h3><p>Each site's odds become chances with its cut removed, then are averaged
with equal weight. That gives every outcome's expected chance.</p></div>
<div class=card><h3>Find the bets that beat it.</h3><p>A bet is listed when a site's odds pay more than its expected chance
deserves. Gaps over 25% are left out as likely stale or mistyped prices.</p></div>
</div>
</div></section>

<section class=section><div class=wrap>
<h2>What's covered.</h2>
<ul class=facts>
<li><b>Sportsbooks:</b> {e(', '.join(books))}.</li>
<li><b>Prediction markets:</b> {e(' and '.join(markets))}.</li>
<li><b>Competitions:</b> {e(', '.join(leagues))}.</li>
<li><b>Bets:</b> match results and total goals for every match; corners, cards, player bets and more on game day.</li>
<li><b>Updates:</b> every morning, New York time. Games that have kicked off drop off the pages on their own.</li>
</ul>
</div></section>

<section class=section><div class=wrap>
<h2>Keeping score.</h2>
<ul class=facts>
<li>Every bet listed on the homepage is saved at the price first shown.</li>
<li>Before kick-off it's checked again against the latest odds. Still being a good bet at kick-off is the fairest test,
because by then the news is in.</li>
<li>After the match it's settled from the final score, assuming $100 on each bet. Corners, cards and player bets can't be
settled from the score alone, so they aren't counted.</li>
<li>Results are on the <a href="index.html">homepage</a>, for the last 7 days and all time.</li>
</ul>
</div></section>

<section class=section><div class=wrap>
<h2>Bet responsibly.</h2>
<div class=help>
<p>This is a study of pricing, not betting advice. A bet that beats what's expected still loses often.</p>
<p>You must be of legal age (21 in most states) and in a state where sports betting is legal.</p>
<p>If gambling stops being fun, call or text <b>1-800-GAMBLER</b>.</p>
</div>
</div></section>

<section class=section><div class=wrap>
<h2>Who made it.</h2>
<p class=sub>Hugh O’Donnell, as a data science project in Python. The code is on <a href="{theme.REPO_URL}">GitHub</a>.</p>
</div></section>
{theme.footer()}
</body></html>"""


if __name__ == "__main__":
    (ROOT / "docs" / "about.html").write_text(build())
    print("wrote docs/about.html")
