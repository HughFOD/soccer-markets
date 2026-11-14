"""The research page (docs/research.html): how accurate are soccer betting odds?

Built from output/results.json. The charts are interactive SVG drawn in the page (markets/viz.py).
Run: python -m markets.research
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pandas as pd

from . import viz
from . import theme
from .website import LG, facts, p

ROOT = Path(__file__).resolve().parent.parent

EXTRA_CSS = """
.toc{columns:2;column-gap:28px;padding:0;list-style:none;margin:0}.toc li{break-inside:avoid;margin-bottom:10px}
.toc a{color:var(--ink);font-size:16px;display:flex;gap:12px;align-items:baseline}.toc a:hover{color:var(--link);text-decoration:none}
.toc a b{color:var(--muted);font-size:13px;font-family:var(--mono);font-weight:600;font-variant-numeric:tabular-nums}
.short{background:var(--bg2);border:1px solid var(--hair);border-radius:var(--r);padding:20px 24px 8px;margin:6px 0 26px}
.short h3{margin:0 0 10px;font-size:17px}.short ul{margin:0;padding-left:20px}.short li{margin:0 0 12px;font-size:16px;line-height:1.5}
.short a{color:var(--link)}
.finding{background:var(--tile);border:1px solid var(--line);border-top:3px solid var(--ink);border-radius:var(--r);padding:26px 28px 20px;margin:0 0 22px}
.finding .n{font:600 12px var(--mono);color:var(--link);margin-bottom:6px;letter-spacing:.06em}
.finding h3{font-size:clamp(21px,2.6vw,26px);line-height:1.2;font-weight:700;margin:0 0 10px}
.finding .take{font-size:17px;line-height:1.5;color:var(--ink2);margin:0 0 22px}
.finding p{color:var(--muted);font-size:15px;line-height:1.55}
.finding .chart{background:var(--tile);border:1px solid var(--hair);border-radius:var(--r);padding:22px 22px 14px;margin:0 0 18px}
.finding table{min-width:0}.finding .tw{margin:12px 0}
.section ul.plain{color:var(--muted);padding-left:20px}.section ul.plain li{margin:8px 0}
.section ul.plain b{color:var(--ink)}
.callout{margin:26px 0 0;font-size:19px;line-height:1.45;color:var(--ink2)}
@media (max-width:720px){.toc{columns:1}.finding{padding:26px 18px 18px;border-radius:var(--r)}.finding .chart{padding:16px 12px 10px}}
"""


def dollars(x: float, signed: bool = False) -> str:
    """-0.064 -> '$6' (per $100 bet), or '−$6' / '+$6' when signed."""
    v = 100 * x
    if not signed:
        return f"${abs(v):.0f}"
    return f"−${-v:.0f}" if v <= -0.5 else (f"+${v:.0f}" if v >= 0.5 else "$0")


def an(s: str) -> str:
    """'a' or 'an' before a percentage: an 80%, an 11%, an 18%, a 70%."""
    s = str(s).lstrip()
    return "an" if s.startswith("8") or re.match(r"1[18](\D|$)", s) else "a"


def _finding(n: int, slug: str, title: str, take: str, body: str, pic: str = "") -> tuple[str, str]:
    return (f'<li><a href="#{slug}"><b>{n:02d}</b>{title}</a></li>',
            f'<div class=finding id="{slug}"><div class=n>FINDING {n}</div><h3>{title}</h3>'
            f'<p class=take>{take}</p>{pic}{body}</div>')



def promoted_html(ea: dict | None) -> str:
    """One paragraph: newly promoted teams in their first ten games, chance given against how often they won."""
    if not ea or not ea.get("promoted"):
        return ""
    ne = ea["promoted"]["new_early"]
    P = lambda x: p(x, 0, False)
    return (f"<p>Newly promoted teams are priced fairly too. In their first ten games back up, the odds gave them "
            f"{an(P(ne['priced']))} {P(ne['priced'])} chance of winning, and they won {P(ne['happened'])} of the time. "
            f"Backing them lost more ({dollars(ne['ret']['est'])} per $100) only because they're usually long shots.</p>")

def sites_html(board: pd.DataFrame | None) -> tuple[str, str] | None:
    """Which site pays the most: match-result odds at each site, best first. Sites pricing under a quarter of the
    matches go below a line, since a handful of matches says little."""
    if board is None or not len(board):
        return None
    e = html.escape
    b = board.copy()
    b["few"] = b["matches"] < 0.25 * b["matches"].max()
    b = b.sort_values(["few", "best_share"], ascending=[True, False])
    top = max(b["best_share"].max(), 1e-9)
    row = lambda r: (f"<tr><td><b>{e(r['name'])}</b><br><span class=kind>{e(r['kind'])}"
                     f"{' · ' + e(r['only']) + ' only' if r.get('only') else ''}</span></td>"
                     f"<td class=num><span class=bar style='width:{60 * r['best_share'] / top:.0f}px'></span>{100 * r['best_share']:.0f}%</td>"
                     f"<td class=num>{100 * r['margin']:.1f}%</td><td class=num>{int(r['matches'])}</td></tr>")
    ranked = "".join(row(r) for _, r in b[~b["few"]].iterrows())
    few = b[b["few"]]
    rest = (f"<tr><td colspan=4 class=kind style='padding-top:14px'>Too few matches to rank</td></tr>"
            + "".join(row(r) for _, r in few.iterrows())) if len(few) else ""
    lead = b[~b["few"]].iloc[0] if (~b["few"]).any() else b.iloc[0]
    take = (f"No single site is always best. Today the site with the best odds most often, {e(lead['name'])}, "
            f"still had the best price on only {100 * lead['best_share']:.0f}% of results, so it pays to check every bet.")
    body = (f"<p>This updates every morning from the US sites' match-result odds. \"Best odds\" is how "
            f"often a site paid the most on a result it offered (ties count for every site, so the column adds up to more than "
            f"100%). The cut is the site's typical built-in margin; smaller is better.</p><div class=tw><table><tr><th>Site</th>"
            f"<th class=num>Best odds</th><th class=num>Site's cut</th><th class=num>Matches priced</th></tr>{ranked}{rest}</table></div>"
            f"{vs_html(b)}")
    return take, body


def vs_html(b: pd.DataFrame) -> str:
    """Sportsbooks against prediction markets: typical cut and how often each kind has the best odds."""
    k = b[~b["few"]].groupby("kind").agg(cut=("margin", "median"), best=("best_share", "mean"), n=("name", "count"))
    if not {"Sportsbook", "Prediction market"} <= set(k.index):
        return ""
    s, p = k.loc["Sportsbook"], k.loc["Prediction market"]
    cheaper = "prediction markets" if p["cut"] < s["cut"] else "sportsbooks"
    return (f"<h4 style='margin:22px 0 6px;font-size:16px'>Sportsbooks against prediction markets</h4><p>After their trading fees, "
            f"the prediction markets take a typical cut of <b>{100 * p['cut']:.1f}%</b>, against <b>{100 * s['cut']:.1f}%</b> for "
            f"the sportsbooks, so {cheaper} are cheaper today. A prediction market has the best odds on "
            f"<b>{100 * p['best']:.0f}%</b> of results, a sportsbook on <b>{100 * s['best']:.0f}%</b> (average per site). "
            "The bigger question, whose odds are more accurate, needs a few hundred finished matches. Every morning's odds "
            "are now saved, so that test runs once there are enough.</p>")


def build(R: dict, curve: pd.DataFrame | None = None, board: pd.DataFrame | None = None, studies: dict | None = None) -> str:
    f = facts(R)
    avg = R["longshot"]["average"]
    fav_band = viz.band_label(avg[0]["odds"])
    long_band = viz.band_label(avg[-1]["odds"])
    items = []
    P = lambda x: p(x, 0, False)   # 0.237 -> '24%'

    c = R["calibration"]["pooled"]
    items.append(("accurate", "The odds are accurate",
                  f"Strong favorites that the odds gave {an(f['top_priced'])} {f['top_priced']} chance of winning actually won "
                  f"{f['top_happened']} of the time. Long shots given {an(f['low_priced'])} {f['low_priced']} chance won "
                  f"{f['low_happened']} of the time. So the odds are close to the truth.",
                  "<p>They're slightly off in one consistent way: favorites win a little more often than their odds "
                  "suggest, and long shots a little less. (Technically, a calibration slope of "
                  f"{c['slope']:.2f}, 95% range {c['slope_lo']:.2f} to {c['slope_hi']:.2f}, where 1.00 would be perfect.)</p>",
                  viz.calibration(R["calibration"]["table"])))

    best = R["longshot"].get("best") or []
    items.append(("longshots", "Long shots are the worst bet",
                  f"Betting $100 on every heavy favorite ({fav_band}) lost {dollars(avg[0]['return'])} on average. "
                  f"Betting $100 on every long shot ({long_band}) lost {dollars(avg[-1]['return'])}.",
                  (f"<p>At the best price across bookmakers, heavy favorites returned {dollars(best[0]['return'], True)} per $100 "
                   f"and long shots {dollars(best[-1]['return'], True)}.</p>" if best else ""),
                  viz.longshot(avg)))


    if R.get("closing"):
        cl = R["closing"]
        top = max(m["threshold"] for m in cl["moves"])
        mv = {m["direction"]: m for m in cl["moves"] if abs(m["threshold"] - top) < 1e-9}
        moves = mv
        every = cl.get("bet_all_open")
        items.append(("line-moves", "When odds change before kick-off, they're usually right to do so",
                      f"Odds move as news comes in. The bigger the move, the more it mattered: when a team's chance rose by "
                      f"{100 * top:.0f} or more percentage points before the match (say, from 40% to {40 + 100 * top:.0f}%), "
                      f"an early $100 bet on it made {dollars(mv['shortened']['return'], True)}. When its chance fell by "
                      f"{100 * top:.0f} or more, the same bet lost {dollars(mv['drifted']['return'])}."
                      + (f" Betting every result at the first odds lost {dollars(every['return'])}." if every else "")
                      + " That's why every pick on this site is checked again at kick-off.",
                      f"<p>Late news, like injuries and team sheets, moves the odds in the right direction. "
                      f"The odds at kick-off were also more accurate than the first odds offered "
                      f"(error score {f['ll_close']} against {f['ll_open']}; lower is better). "
                      f"Based on {f['cl_matches']} matches, {f['cl_years']}.</p>",
                      viz.line_moves(cl["moves"], every)))

    cs = R.get("consensus")
    if cs and cs.get("rules"):
        r2 = next((x for x in cs["rules"] if abs(x["threshold"] - 0.02) < 1e-9), cs["rules"][0])
        items.append(("flagged", "This site's flagged bets usually hold up at kick-off",
                      f"A flagged bet is one where a site pays more than the bet's chance of winning deserves. Of bets flagged "
                      f"with a gap of {100 * r2['threshold']:.0f}% or more, {100 * r2['beat_close']:.0f}% were still good bets at "
                      f"kick-off, when the odds are at their most accurate, worth {100 * r2['edge_vs_close']:.1f}% per bet on average. "
                      "The bigger the gap, the more often it held up.",
                      f"<p>Gap of {100 * r2['threshold']:.0f}%+: worth {100 * r2['edge_vs_close']:.1f}% per bet at kick-off, "
                      f"95% range {100 * r2['lo']:.1f}% to {100 * r2['hi']:.1f}%. Tested on {len(cs['books'])} European bookmakers, "
                      f"{cs['seasons'][0][:4]} to {cs['seasons'][-1][:4]} ({cs['matches']:,} matches), because old odds from "
                      "American sites aren't available for free. Actual wins and losses over a few hundred bets swing too much "
                      "to prove anything, so the kick-off odds are the fairer test.</p>",
                      viz.flagged(cs["rules"])))

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
                      f"<p>Slight favorites leading 1–0 at half-time were given {an(P(lead['model_win']))} {P(lead['model_win'])} chance to win and won {P(lead['actual_win'])} "
                      f"of the time ({lead['matches']:,} matches). Games level at half-time were given {an(P(lvl['model_draw']))} {P(lvl['model_draw'])} chance of a draw "
                      f"and ended level {P(lvl['actual_draw'])} of the time.</p>"
                      + checks,
                      viz.score_effects(lv["score_effects"])))

    S = studies or {}
    cw = S.get("crowds")
    if cw:
        b, em, af = cw["before"], cw["empty"], cw["after"]
        mo = cw.get("monthly", [])
        months = [pd.Period(r["month"]).strftime("%b %y") for r in mo]
        pic = viz.chart("crowds", "Home wins in empty stadiums, month by month",
                        "Blue: how often the home team actually won. Orange: how often the odds expected it to.",
                        {"type": "line", "x": months, "ticks": months, "fmt": "pct", "from0": False,
                         "series": [{"name": "actual", "values": [round(100 * r["happened"], 1) for r in mo], "color": "a"},
                                    {"name": "odds expected", "values": [round(100 * r["priced"], 1) for r in mo], "color": "b"}]},
                        viz._table(["Month", "Home wins", "Odds expected", "Matches"],
                                   [[m_, f"{100 * r['happened']:.0f}%", f"{100 * r['priced']:.0f}%", r["matches"]] for m_, r in zip(months, mo)]))
        items.append(("crowds", "Home advantage matters",
                      f"Playing at home is a real edge: in the five seasons before COVID, home teams won {P(b['happened'])} of "
                      f"matches and scored {b['goal_diff']:+.2f} goals a game more than their opponents. When stadiums were empty "
                      f"(June 2020 to May 2021), that edge roughly halved: home teams won {P(em['happened'])} and the goal margin "
                      f"fell to {em['goal_diff']:+.2f}. The odds were slow to notice, so for the first months home teams were overrated.",
                      f"<p>The gap was widest in autumn 2020 and had closed by January 2021. Since fans returned, home teams have won "
                      f"{P(af['happened'])} of matches, with the odds expecting {P(af['priced'])}. Based on {b['matches']:,} matches "
                      f"before, {em['matches']:,} in empty stadiums and {af['matches']:,} after.</p>", pic))
    dr = S.get("draws")
    if dr and dr.get("draw_same"):
        ds, ws = dr["draw_same"], dr["win_same"]
        pic = viz.chart("draws", "Same chance, different result",
                        "Average result of a $100 bet on outcomes the odds gave a 20–35% chance",
                        {"type": "hbar", "labels": ["Bet on the draw", "Bet on a team to win"],
                         "values": [round(100 * ds["ret"]["est"]), round(100 * ws["ret"]["est"])], "colors": ["a", "b"],
                         "fmt": "usd", "unit": "per $100 bet", "notes": [f"{ds['ret']['n']:,} bets", f"{ws['ret']['n']:,} bets"]},
                        viz._table(["Bet (20–35% chance)", "Odds expected", "Happened", "Per $100"],
                                   [["Draw", f"{100 * ds['priced']:.1f}%", f"{100 * ds['happened']:.1f}%", dollars(ds['ret']['est'], True)],
                                    ["Team to win", f"{100 * ws['priced']:.1f}%", f"{100 * ws['happened']:.1f}%", dollars(ws['ret']['est'], True)]]))
        items.append(("draws", "Draws are a better bet than wins at the same odds",
                      f"Take every bet the odds gave a 20–35% chance. Betting $100 on the draw lost {dollars(ds['ret']['est'])} on average. "
                      f"Betting $100 on a team to win lost {dollars(ws['ret']['est'])}. Both lose, because of the cut, but draws lose less.",
                      f"<p>That's because draws happen about as often as the odds say ({P(ds['priced'])} expected, {P(ds['happened'])} "
                      f"happened), while teams given the same chance win a little less often than expected ({P(ws['priced'])} expected, "
                      f"{P(ws['happened'])} happened).</p>", pic))
    pp = S.get("popular")
    if pp and pp.get("others_matched") is not None:
        rows = [r for r in pp["bands"] if r["popular"]]
        pic = viz.chart("popular", "Big clubs only look better because they're usually favorites",
                        "Average result of a $100 bet on a team to win",
                        {"type": "hbar", "labels": ["Big clubs", "Other teams, all bets", "Other teams, at the same odds as big clubs"],
                         "values": [round(100 * pp["popular"]["est"]), round(100 * pp["others"]["est"]), round(100 * pp["others_matched"])],
                         "colors": ["a", "b", "b"], "fmt": "usd", "unit": "per $100 bet",
                         "notes": [f"{pp['popular']['n']:,} bets", f"{pp['others']['n']:,} bets", "weighted to match the big clubs' odds"]},
                        viz._table(["Chance the odds gave", "Big clubs, per $100", "Bets", "Other teams, per $100", "Bets"],
                                   [[r["band"], dollars(r["popular"]["est"], True), f"{r['popular']['n']:,}",
                                     dollars(r["others"]["est"], True), f"{r['others']['n']:,}"] for r in rows]))
        items.append(("popular", "Big clubs aren't overpriced",
                      "Fans back big clubs no matter what, so you might expect their odds to be worse. At first glance it's the "
                      f"opposite: betting $100 on a big club to win lost {dollars(pp['popular']['est'])} on average, against "
                      f"{dollars(pp['others']['est'])} for other teams. But big clubs are usually favorites (a "
                      f"{P(pp['pop_chance'])} chance on average), and favorites lose less (Finding 2). Compare other teams at the "
                      f"same odds and they lost {dollars(pp['others_matched'])} too. So big clubs are priced just like everyone else.",
                      f"<p>Betting against the big clubs was the worst of all: backing their opponents lost "
                      f"{dollars(pp['against']['est'])} per $100, mostly because those opponents are usually long shots. "
                      "Big clubs here: " + ", ".join(pp["teams"]) + ".</p>" + promoted_html(S.get("early")), pic))

    to = S.get("totals")
    if to and to.get("bands"):
        bd = to["bands"]
        lo_b, hi_b = bd[0], bd[-1]
        ov, un = to["sides"]["Over 2.5"], to["sides"]["Under 2.5"]
        pic = viz.chart("totals", "The less likely side loses more",
                        "Average result of a $100 bet on over or under 2.5 goals, by the chance the odds gave it",
                        {"type": "hbar", "labels": [b["band"] for b in bd], "values": [round(100 * b["ret"]["est"], 1) for b in bd],
                         "fmt": "usd", "unit": "per $100 bet", "notes": [f"{b['ret']['n']:,} bets" for b in bd]},
                        viz._table(["Chance the odds gave", "Odds expected", "Happened", "Per $100", "Bets"],
                                   [[b["band"], f"{100 * b['priced']:.0f}%", f"{100 * b['happened']:.0f}%",
                                     dollars(b["ret"]["est"], True), f"{b['ret']['n']:,}"] for b in bd]))
        items.append(("totals", "The long-shot pattern holds for total goals too",
                      f"Over/under 2.5 goals works like match results. When the odds made a side unlikely (under 35%), "
                      f"$100 on it lost {dollars(lo_b['ret']['est'])} on average. When they made it likely (65% or more), it lost "
                      f"only {dollars(hi_b['ret']['est'])}.",
                      f"<p>The unlikely side happened {P(lo_b['happened'])} of the time against {P(lo_b['priced'])} expected; the "
                      f"likely side {P(hi_b['happened'])} against {P(hi_b['priced'])}. Overs and unders cost about the same overall: "
                      f"each lost about {dollars((ov['ret']['est'] + un['ret']['est']) / 2)} per $100 at the average price. Based on "
                      f"{to['matches']:,} matches since 2005.</p>", pic))
    sk = S.get("stakes")
    if sk and sk.get("motivated_vs_not"):
        mv, nm, bo = sk["motivated_vs_not"], sk["not_vs_motivated"], sk["both"]
        rows_ = [("Had something to play for, against a team with nothing", "Something to play for", mv),
                 ("Had nothing to play for, against a team with something", "Nothing to play for", nm),
                 ("Both teams had something to play for", "Both had something", bo)]
        pic = viz.chart("stakes", "Teams won about as often as the odds expected",
                        "How often each team won in the last eight games of a season, with the chance the odds gave it",
                        {"type": "hbar", "labels": [f"{r[1]} (expected {100 * r[2]['priced']:.1f}%)" for r in rows_], "values": [round(100 * r[2]["happened"], 1) for r in rows_],
                         "fmt": "pct1", "unit": "won", "notes": [f"odds expected {100 * r[2]['priced']:.1f}%" for r in rows_]},
                        viz._table(["Team", "Odds expected", "Won", "Per $100", "Bets"],
                                   [[r[0], f"{100 * r[2]['priced']:.1f}%", f"{100 * r[2]['happened']:.1f}%",
                                     dollars(r[2]["ret"]["est"], True), f"{r[2]['ret']['n']:,}"] for r in rows_]))
        items.append(("stakes", "Teams with nothing to play for aren't overpriced",
                      f"Late in the season, some teams can't reach Europe or promotion and can't be relegated. Against a team that "
                      f"still had something to play for, the team with something at stake was given {an(P(mv['priced']))} "
                      f"{P(mv['priced'])} chance and won {P(mv['happened'])} of the time. That gap could easily be luck, so the odds "
                      f"already account for motivation.",
                      f"<p>Based on the last eight games of every finished season ({sk['matches']:,} matches). Nothing to play for "
                      f"means already safe from relegation and unable to reach the top seven (top six in the Championship, "
                      f"top five in Ligue 1), worked out from the league table before each match.</p>", pic))

    st = sites_html(board)
    if st:
        items.append(("sites", "Which site pays the most today", st[0], st[1]))

    order = ["accurate", "longshots", "totals", "line-moves", "flagged", "half-time", "crowds", "draws", "popular", "stakes",
             "sites"]
    items.sort(key=lambda it: order.index(it[0]) if it[0] in order else len(order))
    toc, body = [], []
    num = {it[0]: i for i, it in enumerate(items, 1)}
    for i, it in enumerate(items, 1):
        a, b = _finding(i, *it)
        toc.append(a)
        body.append(b)
    # the five results to read if you read nothing else, each linking to its finding
    short = []
    see = lambda k: f" <a href=#{k}>Finding {num[k]}</a>" if k in num else ""
    if "longshots" in num:
        short.append(f"<b>Long shots are the worst bet.</b> $100 on every long shot lost {dollars(avg[-1]['return'])} on average; "
                     f"on every heavy favorite, {dollars(avg[0]['return'])}.{see('longshots')}")
    to = S.get("totals")
    if "totals" in num and to:
        short.append(f"<b>The same holds for total goals.</b> The unlikely side of over/under 2.5 lost "
                     f"{dollars(to['bands'][0]['ret']['est'])} per $100; the likely side {dollars(to['bands'][-1]['ret']['est'])}.{see('totals')}")
    if "line-moves" in num:
        short.append(f"<b>When odds move before kick-off, they're usually right.</b> An early bet on a team whose chance then rose "
                     f"{100 * top:.0f}+ points made {dollars(moves['shortened']['return'], True)} per $100.{see('line-moves')}")
    if "flagged" in num:
        short.append(f"<b>This site's method holds up.</b> {100 * r2['beat_close']:.0f}% of prices flagged as {100 * r2['threshold']:.0f}%+ "
                     f"better than the consensus were still better at kick-off.{see('flagged')}")
    if "half-time" in num:
        short.append(f"<b>Teams behind at half-time score more than the odds expect:</b> {P(se[-2]['ratio'] - 1)} more for teams "
                     f"losing by 2 or more.{see('half-time')}")
    short_html = (f"<div class=short><h3>In short</h3><ul>{''.join(f'<li>{x}</li>' for x in short)}</ul></div>"
                  if short else "")

    return f"""<!doctype html><html lang=en><head>{theme.HEAD}
{theme.meta("research.html", "How accurate are betting odds? · Today's Soccer Bets", f"What {int(R['seasons'][-1][:4]) - int(R['seasons'][0][:4])} years of soccer betting odds show about how accurate the odds are.")}
<style>{theme.CSS}{EXTRA_CSS}{viz.CSS}</style></head><body>
{theme.nav("research")}
<section class=hero><div class=wrap>
<p class=eyebrow>Research</p>
<h1>How accurate are betting odds?</h1>
<p class=lede>{f['matches']} matches from six top European leagues since {R['seasons'][0][:4]}, checked against their betting odds.</p>
<div class=ctas><a class=btn href="#found">See the findings</a><a class="btn ghost" href="index.html">Today's best bets</a></div>
</div></section>

<section class=section id=found><div class=wrap>
<h2>What I found.</h2>
{short_html}<ul class=toc>{''.join(toc)}</ul>
</div></section>
<div class=wrap>{''.join(body)}</div>

<section class=band><div class=wrap>
<h2>How it's built.</h2>
<ul class=plain>
<li><b>Data.</b> Results and odds from every bookmaker recorded for each match, from <a href="https://www.football-data.co.uk">football-data.co.uk</a>.</li>
<li><b>Removing the cut.</b> Three methods compared: proportional, power and Shin's 1993 model.</li>
<li><b>Uncertainty.</b> 95% ranges from resampling whole matches (the bootstrap).</li>
<li><b>Tests.</b> Automated checks on every calculation.</li>
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
    sb = out_dir / "site_scoreboard.csv"     # written by the daily update (markets.weekly)
    board = pd.read_csv(sb).fillna({"only": ""}) if sb.exists() else None
    sj = out_dir / "studies.json"     # written by python -m markets.studies
    studies = json.loads(sj.read_text()) if sj.exists() else None
    (docs / "research.html").write_text(build(R, curve, board, studies))
    print(f"wrote {docs / 'research.html'}")


if __name__ == "__main__":
    main()
