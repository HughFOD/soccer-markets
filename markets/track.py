"""Track record: how the homepage's bets actually turned out.

Every morning (markets.weekly):
  1. record  - every bet the homepage lists is saved to data/track_record.csv, once, at the price
               and site first shown.
  2. update  - while the match is still to come, each saved bet is re-checked against the latest
               expected chance: would the price first shown still beat what's expected now? The last
               check before kick-off is the fairest test of whether a bet was really good value,
               because by then more news is in.
  3. grade   - after the match, the final score from The Odds API decides results, goals totals,
               handicaps, both-teams-to-score and draw-no-bet bets. Corners, cards and player bets
               need match statistics the scores don't include: corners and cards in the six leagues are settled
               from football-data.co.uk results files (grade_stats); player bets are marked "not graded".

Profit assumes $100 on every bet at the price first shown.
"""
from __future__ import annotations

import html
import re
import json
import urllib.request

import numpy as np
import pandas as pd

from .usbooks import ROOT, SPORTS, american

LEDGER = ROOT / "data" / "track_record.csv"
COLS = ["key", "flagged_at", "kickoff", "league", "id", "home", "away", "match", "bet", "kind", "outcome", "point",
        "sites", "n_sites", "odds", "chance", "edge", "last_checked", "last_chance", "last_value", "result", "profit"]
GRADABLE = {"result", "totals", "alternate_totals", "alternate_spreads", "btts", "draw_no_bet"}
SETTLE_HOURS = 2.5   # a match is treated as finished this long after kick-off
MAX_ROWS = 500       # settled bets listed on the homepage (newest first)
GIVE_UP_DAYS = 3     # the scores endpoint only looks back 3 days

# Corners and cards are settled from football-data.co.uk results files, which record each game's corners
# and yellow and red cards for these leagues. The files are updated a few times a week, so these bets wait
# up to STATS_DAYS for their game to appear.
STATS_KINDS = {"alternate_totals_corners", "alternate_team_totals_corners", "alternate_spreads_corners",
               "corners_1x2", "alternate_totals_cards", "alternate_spreads_cards"}
STATS_LEAGUES = {"Premier League": "E0", "Championship": "E1", "La Liga": "SP1", "Bundesliga": "D1",
                 "Serie A": "I1", "Ligue 1": "F1"}
STATS_DAYS = 10


def load() -> pd.DataFrame:
    if LEDGER.exists():
        L = pd.read_csv(LEDGER, dtype={"result": str, "outcome": str, "key": str, "id": str})
        L["result"] = L["result"].fillna("")
        return L
    return pd.DataFrame(columns=COLS)


def save(L: pd.DataFrame) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    L[COLS].to_csv(LEDGER, index=False)


def bet_key(b: dict) -> str:
    point = "" if b.get("point") is None or pd.isna(b.get("point")) else f"{float(b['point']):g}"
    return f"{b['id']}|{b['kind']}|{b['outcome']}|{point}"


def record(L: pd.DataFrame, days: list, now: pd.Timestamp) -> pd.DataFrame:
    """Add every listed bet not already in the ledger."""
    have = set(L["key"]) if len(L) else set()
    new = []
    for _, bets in days:
        for b in bets:
            k = bet_key(b)
            if k in have:
                continue
            have.add(k)
            home, away = b["match"].split(" v ", 1)
            new.append({"key": k, "flagged_at": now.isoformat(), "kickoff": pd.Timestamp(b["ko"]).isoformat(),
                        "league": b["league"], "id": b["id"], "home": home, "away": away, "match": b["match"],
                        "bet": b["bet"], "kind": b["kind"], "outcome": b["outcome"], "point": b.get("point"),
                        "sites": ", ".join(b["sites"]), "n_sites": b.get("n_sites"), "odds": b["dec"],
                        "chance": b["chance"], "edge": b["edge"], "last_checked": now.isoformat(),
                        "last_chance": b["chance"], "last_value": b["edge"], "result": "", "profit": np.nan})
    if not new:
        return L
    N = pd.DataFrame(new, columns=COLS)
    return N if not len(L) else pd.concat([L, N], ignore_index=True)


def update(L: pd.DataFrame, everything: list, now: pd.Timestamp) -> pd.DataFrame:
    """Re-check bets whose match hasn't started against the latest expected chance."""
    if not len(L):
        return L
    latest = {bet_key(b): b["chance"] for b in everything}
    ko = pd.to_datetime(L["kickoff"], utc=True)
    for i in L.index[(ko > now) & (L["result"] == "")]:
        c = latest.get(L.at[i, "key"])
        if c is None or not np.isfinite(c):
            continue
        L.at[i, "last_chance"] = c
        L.at[i, "last_value"] = c * float(L.at[i, "odds"]) - 1
        L.at[i, "last_checked"] = now.isoformat()
    return L


# ---- grading -------------------------------------------------------------------------------------

def _line(margin: float) -> int:
    """+1 win, 0 push (stake back), -1 loss, for a margin over the line."""
    return 1 if margin > 0 else 0 if margin == 0 else -1


def _asian(margin_at_zero: float, point: float) -> list[tuple[float, int]]:
    """Lines ending in .25 or .75 are two half-bets on the neighbouring lines; others are one bet."""
    if abs((point * 4) % 2) == 1:
        return [(0.5, _line(margin_at_zero + point - 0.25)), (0.5, _line(margin_at_zero + point + 0.25))]
    return [(1.0, _line(margin_at_zero + point))]


def settle(row, hg: int, ag: int) -> list[tuple[float, int]] | None:
    """[(share of stake, +1 win / 0 push / -1 loss), ...], or None if the score can't settle it."""
    kind, out = row["kind"], str(row["outcome"])
    point = float(row["point"]) if pd.notna(row["point"]) else 0.0
    if kind == "result":
        actual = "h" if hg > ag else "a" if ag > hg else "d"
        return [(1.0, 1 if out == actual else -1)]
    if kind in ("totals", "alternate_totals"):
        total = hg + ag
        if out == "Over":
            return _asian(total, -point)
        if out == "Under":
            return _asian(-total, point)
        return None
    if kind == "alternate_spreads":
        if out == row["home"]:
            return _asian(hg - ag, point)
        if out == row["away"]:
            return _asian(ag - hg, point)
        return None
    if kind == "btts":
        return [(1.0, 1 if (out == "Yes") == (hg > 0 and ag > 0) else -1)]
    if kind == "draw_no_bet":
        if hg == ag:
            return [(1.0, 0)]
        winner = row["home"] if hg > ag else row["away"]
        return [(1.0, 1 if out == winner else -1)]
    return None


def settle_stats(row, st: dict) -> list[tuple[float, int]] | None:
    """Corner and card bets from one game's statistics: st has hc, ac (corners) and hcards, acards."""
    kind, out = row["kind"], str(row["outcome"])
    point = float(row["point"]) if pd.notna(row["point"]) else 0.0
    what = "corners" if "corners" in kind else "cards"
    h, a = st["h" + ("c" if what == "corners" else "cards")], st["a" + ("c" if what == "corners" else "cards")]
    if kind in ("alternate_totals_corners", "alternate_totals_cards"):
        total = h + a
    elif kind == "alternate_team_totals_corners":         # the bet's name starts with the team it's about
        bet = str(row["bet"])
        total = h if bet.startswith(str(row["home"])) else a if bet.startswith(str(row["away"])) else None
        if total is None:
            return None
    elif kind in ("alternate_spreads_corners", "alternate_spreads_cards"):
        if out == row["home"]:
            return _asian(h - a, point)
        if out == row["away"]:
            return _asian(a - h, point)
        return None
    elif kind == "corners_1x2":
        actual = row["home"] if h > a else row["away"] if a > h else "Draw"
        return [(1.0, 1 if out == actual else -1)]
    else:
        return None
    if out == "Over":
        return _asian(total, -point)
    if out == "Under":
        return _asian(-total, point)
    return None


def _norm(name: str) -> str:
    """Team name in a form both sources share: lower case, no accents, common short forms spelled out."""
    import unicodedata
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    for a, b in (("man united", "manchester united"), ("man city", "manchester city"), ("nott'm", "nottingham"),
                 ("wolves", "wolverhampton"), ("sheffield weds", "sheffield wednesday"), ("qpr", "queens park rangers"),
                 ("west brom", "west bromwich"), ("ath madrid", "atletico madrid"), ("ath bilbao", "athletic bilbao"),
                 ("espanol", "espanyol"), ("sociedad", "real sociedad"), ("betis", "real betis"),
                 ("m'gladbach", "monchengladbach"), ("ein frankfurt", "eintracht frankfurt"), ("fc koln", "koln"),
                 ("paris sg", "paris saint germain"), ("st etienne", "saint etienne"), ("inter", "inter milan"),
                 ("leverkusen", "bayer leverkusen"), ("fortuna dusseldorf", "dusseldorf"), ("vallecano", "rayo vallecano")):
        if s == a or s.startswith(a + " "):
            s = b + s[len(a):]
    for w in (" fc", "fc ", " afc", "afc ", " cf", " sc", "1. ", " 1907", " 1846", " 04", " 05", " bc", "ac ", "as ", "ss ",
              "ogc ", "rc ", "stade ", "real club de ", "rcd ", "vfb ", "vfl ", "tsg ", "sv ", "fsv ", "&"):
        s = s.replace(w, " ")
    return " ".join(s.replace("-", " ").replace(".", " ").split())


def _similar(a: str, b: str) -> float:
    import difflib
    a, b = _norm(a), _norm(b)
    if a == b:
        return 1.0
    if a in b or b in a:                  # "leverkusen" in "bayer leverkusen": a match, but an exact one wins
        return 0.9
    return difflib.SequenceMatcher(None, a, b).ratio()


def fetch_stats(needed: set[tuple[str, str]]) -> dict:
    """{(league code, season code): DataFrame of that season's games} from football-data.co.uk."""
    import io
    out = {}
    for lg, season in sorted(needed):
        url = f"https://www.football-data.co.uk/mmz4281/{season}/{lg}.csv"
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                out[(lg, season)] = pd.read_csv(io.BytesIO(r.read()), encoding="latin-1")
        except Exception as e:
            print(f"  no stats file {lg} {season}: {e}")
    return out


def _season(ko: pd.Timestamp) -> str:
    y = ko.year if ko.month >= 7 else ko.year - 1
    return f"{y % 100:02d}{(y + 1) % 100:02d}"


def find_game(files: dict, row) -> dict | None:
    """The game's corners and cards, matched by league, date (UK time) and the closest team names."""
    lg = STATS_LEAGUES.get(row["league"])
    ko = pd.Timestamp(row["kickoff"]).tz_convert("Europe/London")
    d = files.get((lg, _season(ko)))
    if d is None or not len(d):
        return None
    dates = pd.to_datetime(d["Date"], dayfirst=True, errors="coerce").dt.date
    day = d[dates == ko.date()]
    best, score = None, 0.0
    for _, g in day.iterrows():
        s = min(_similar(row["home"], g["HomeTeam"]), _similar(row["away"], g["AwayTeam"]))
        if s > score:
            best, score = g, s
    if best is None or score < 0.6:
        return None
    try:
        n = lambda c: int(best[c])
        return {"hc": n("HC"), "ac": n("AC"), "hcards": n("HY") + n("HR"), "acards": n("AY") + n("AR")}
    except (KeyError, ValueError):
        return None


def grade_stats(L: pd.DataFrame, now: pd.Timestamp, files: dict | None = None) -> pd.DataFrame:
    """Settle corner and card bets in the six leagues once their games are in the results files."""
    if not len(L):
        return L
    ko = pd.to_datetime(L["kickoff"], utc=True)
    todo = (L["kind"].isin(STATS_KINDS) & L["league"].isin(STATS_LEAGUES) & L["result"].isin(["", "not graded"])
            & (ko < now - pd.Timedelta(hours=SETTLE_HOURS)))
    if not todo.any():
        return L
    if files is None:
        files = fetch_stats({(STATS_LEAGUES[L.at[i, "league"]], _season(ko[i].tz_convert("Europe/London")))
                             for i in L.index[todo]})
    for i in L.index[todo]:
        st = find_game(files, L.loc[i])
        parts = settle_stats(L.loc[i], st) if st else None
        if parts:
            L.at[i, "profit"], L.at[i, "result"] = profit_and_label(parts, float(L.at[i, "odds"]))
        elif st or ko[i] < now - pd.Timedelta(days=STATS_DAYS):
            L.at[i, "result"] = "not graded" if st else "no stats found"
        else:
            L.at[i, "result"] = ""                                        # wait for the file to catch up
    return L


def profit_and_label(parts: list[tuple[float, int]], odds: float, stake: float = 100.0) -> tuple[float, str]:
    profit = sum(stake * sh * ((odds - 1) if o == 1 else 0 if o == 0 else -1) for sh, o in parts)
    outs = {o for _, o in parts}
    label = ("won" if outs == {1} else "lost" if outs == {-1} else "push" if outs == {0}
             else "half won" if profit > 0 else "half lost")
    return round(profit, 2), label


def sports_needed(L: pd.DataFrame, now: pd.Timestamp) -> list[str]:
    if not len(L):
        return []
    ko = pd.to_datetime(L["kickoff"], utc=True)
    due = L[(L["result"] == "") & L["kind"].isin(GRADABLE) & (ko < now - pd.Timedelta(hours=SETTLE_HOURS))]
    names = {v: k for k, v in SPORTS.items()}
    return sorted({names[x] for x in due["league"] if x in names})


def fetch_scores(api_key: str, sports: list[str]) -> dict:
    """{event id: (home goals, away goals)} for completed matches in the last 3 days (2 credits per league)."""
    out = {}
    for sp in sports:
        url = f"https://api.the-odds-api.com/v4/sports/{sp}/scores/?daysFrom=3&apiKey={api_key}"
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                events = json.loads(r.read())
        except Exception as e:  # a failed league is retried tomorrow
            print(f"  scores for {sp} not available: {e}")
            continue
        for ev in events:
            if not ev.get("completed") or not ev.get("scores"):
                continue
            s = {x["name"]: x["score"] for x in ev["scores"]}
            try:
                out[ev["id"]] = (int(s[ev["home_team"]]), int(s[ev["away_team"]]))
            except (KeyError, TypeError, ValueError):
                continue
    return out


def grade(L: pd.DataFrame, scores: dict, now: pd.Timestamp) -> pd.DataFrame:
    if not len(L):
        return L
    ko = pd.to_datetime(L["kickoff"], utc=True)
    done = ko < now - pd.Timedelta(hours=SETTLE_HOURS)
    for i in L.index[done & (L["result"] == "")]:
        row = L.loc[i]
        if row["kind"] in STATS_KINDS and row["league"] in STATS_LEAGUES:
            continue                                                      # settled by grade_stats
        if row["kind"] not in GRADABLE:
            L.at[i, "result"] = "not graded"
            continue
        if row["id"] in scores:
            parts = settle(row, *scores[row["id"]])
            if parts is None:
                L.at[i, "result"] = "not graded"
                continue
            L.at[i, "profit"], L.at[i, "result"] = profit_and_label(parts, float(row["odds"]))
        elif ko[i] < now - pd.Timedelta(days=GIVE_UP_DAYS):
            L.at[i, "result"] = "no score found"
    return L


# ---- page section ------------------------------------------------------------------------------------

def _usd(x: float) -> str:
    return f"{'+' if x >= 0 else '−'}${abs(x):,.0f}"


def html_section(L: pd.DataFrame, full: bool = False) -> str:
    """Homepage: the summary and a link. full=True (the Results page): also every settled bet, filterable."""
    e = html.escape
    if not len(L):
        return ""
    start = pd.to_datetime(L["flagged_at"], utc=True).min().tz_convert("America/New_York")
    g = L[L["result"].isin(["won", "lost", "push", "half won", "half lost"])].copy()
    checked = L[pd.to_datetime(L["last_checked"], utc=True) > pd.to_datetime(L["flagged_at"], utc=True)]
    still = f"{100 * (checked['last_value'] > 0).mean():.0f}%" if len(checked) else "–"
    intro = (f"Every bet listed on this page since {start:%B %-d, %Y}, is saved at the price first shown. "
             "Before kick-off it's checked again against the latest odds, and after the match it's settled "
             "from the final score. Profit assumes $100 on each bet.")
    if not len(g):
        return (f"<section class=section style=padding-top:0><div class=wrap><h2>How the picks have done.</h2><p class=sub>{intro}</p>"
                f"<p class=sub><b>{len(L)} bets recorded so far.</b> Results appear here once their matches finish."
                + (f" So far, <b>{still}</b> of the bets re-checked before kick-off were still good value." if len(checked) else "")
                + "</p></div></section>")
    n, profit = len(g), g["profit"].sum()
    w, lo = g["result"].isin(["won", "half won"]).sum(), g["result"].isin(["lost", "half lost"]).sum()
    pu = (g["result"] == "push").sum()
    tiles = (f"<div class=stats><div class=stat><div class=v>{w}–{lo}{f'–{pu}' if pu else ''}</div><div class=l>won–lost{'–push' if pu else ''}</div></div>"
             f"<div class=stat><div class=v>{_usd(profit)}</div><div class=l>profit from $100 on each ({100 * profit / (100 * n):+.1f}%)</div></div>"
             f"<div class=stat><div class=v>{100 * g['edge'].mean():+.1f}%</div><div class=l>expected return when listed</div></div></div>")
    # every settled bet, newest first, with buttons to show only won, lost or push
    allbets = g.sort_values("kickoff", ascending=False).head(MAX_ROWS)
    simple = lambda res: "won" if res in ("won", "half won") else "lost" if res in ("lost", "half lost") else "push"
    site1 = lambda r: str(r["sites"]).split(",")[0].strip()
    rows = "".join(
        f"<tr data-r={simple(r['result'])} data-lg=\"{e(r['league'])}\" data-st=\"{e(site1(r))}\">"
        f"<td>{pd.Timestamp(r['kickoff']).tz_convert('America/New_York'):%b %-d}</td><td>{e(r['bet'])}<br><span class=kind>{e(r['match'])}</span></td>"
        f"<td>{e(site1(r))}</td><td class=n>{american(float(r['odds']))}</td>"
        f"<td class=n>{e(r['result'])}</td><td class=n>{_usd(float(r['profit']))}</td></tr>"
        for _, r in allbets.iterrows())
    recent = "".join(re.sub(r"^<tr [^>]*>", "<tr>", x) for x in re.findall(r"<tr data-r.*?</tr>", rows)[:10])
    counts = {"all": len(allbets), "won": int(w), "lost": int(lo), "push": int(pu)}
    buttons = "".join(f'<button class=rfilt data-f={k}{" aria-pressed=true" if k == "all" else ""}>{lab}<span>{counts[k]}</span></button>'
                      for k, lab in (("all", "All"), ("won", "Won"), ("lost", "Lost"), ("push", "Push")) if k != "push" or pu)
    opts = lambda vals, label: f"<option value=''>{label}</option>" + "".join(f"<option>{e(v)}</option>" for v in vals)
    leagues = sorted(allbets["league"].dropna().unique())
    sites = sorted({site1(r) for _, r in allbets.iterrows()})
    filt = (f"<style>.rfilts{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:18px 0 10px}}"
            ".rfilt{font:inherit;font-size:15px;border:0;border-radius:var(--r);padding:8px 16px;background:var(--bg2);color:var(--ink);cursor:pointer}"
            ".rfilt span{margin-left:7px;color:var(--muted);font-size:13px}.rfilt[aria-pressed=true]{background:var(--ink);color:var(--bg)}"
            ".rfilt[aria-pressed=true] span{color:inherit;opacity:.7}"
            ".rsel{font:inherit;font-size:15px;padding:7px 12px;border-radius:var(--r);border:1px solid var(--line);background:var(--bg);color:var(--ink)}"
            ".rcount{font-size:13px;color:var(--muted);margin:6px 0 0}.rmore{font:inherit;font-size:15px;margin:12px 0 0;border:1px solid var(--line);"
            "border-radius:var(--r);padding:8px 18px;background:var(--bg);color:var(--ink);cursor:pointer}"
            "html:not(.js) .rfilts,html:not(.js) .rmore,html:not(.js) .rcount{display:none}</style>"
            f"<div class=rfilts role=group aria-label='Filter bets'>{buttons}"
            f"<select class=rsel id=rlg aria-label=League>{opts(leagues, 'All leagues')}</select>"
            f"<select class=rsel id=rst aria-label=Site>{opts(sites, 'All sites')}</select></div>")
    js = ("<script>document.documentElement.classList.add('js');(function(){var PAGE=15,shown=PAGE,f='all',rows=[].slice.call(document.querySelectorAll('tr[data-r]')),"
          "lg=document.getElementById('rlg'),st=document.getElementById('rst'),more=document.getElementById('rmore'),cnt=document.getElementById('rcount');"
          "function apply(){var n=0;rows.forEach(function(t){var ok=(f==='all'||t.dataset.r===f)&&(!lg.value||t.dataset.lg===lg.value)"
          "&&(!st.value||t.dataset.st===st.value);if(ok)n++;t.hidden=!ok||n>shown});"
          "more.hidden=n<=shown;more.textContent='Show all '+n+' bets';"
          "cnt.textContent=n?'Showing '+Math.min(n,shown)+' of '+n+' bets':'No bets match these filters.'}"
          "document.querySelectorAll('.rfilt').forEach(function(b){b.addEventListener('click',function(){"
          "document.querySelectorAll('.rfilt').forEach(function(x){x.setAttribute('aria-pressed',x===b?'true':'false')});"
          "f=b.dataset.f;shown=PAGE;apply()})});"
          "lg.addEventListener('change',function(){shown=PAGE;apply()});st.addEventListener('change',function(){shown=PAGE;apply()});"
          "more.addEventListener('click',function(){shown=1e9;apply()});apply()})()</script>")
    other = int(L["result"].isin(["not graded", "no stats found"]).sum())
    note = (" Player bets, and corner or card bets outside the six leagues (Premier League, Championship, La Liga, "
            "Bundesliga, Serie A, Ligue 1), aren't counted, because there's no free record of how they ended "
            f"({other} bet{'' if other == 1 else 's'} so far)." if other else "")
    return (f"<section class=section style=padding-top:0><div class=wrap><h2>How the picks have done.</h2><p class=sub>{intro}</p>"
            f"{tiles}"
            f"<p class=note>Wins and losses swing a lot over a few dozen bets, so the profit figure means little until there are "
            f"several hundred.{note}</p>"
            + (f"<h3 class=tally>Every settled bet</h3>{filt}"
               f"<div class=tablewrap><table><tr><th>Date</th><th>Bet</th><th>Site</th><th class=n>Odds</th><th class=n>Result</th>"
               f"<th class=n>Profit on $100</th></tr>{rows}</table></div>"
               f"<p class=rcount id=rcount></p><button class=rmore id=rmore hidden>Show more</button>{js}" if full else
               f"<h3 class=tally>Latest results</h3><div class=tablewrap><table><tr><th>Date</th><th>Bet</th><th>Site</th><th class=n>Odds</th>"
               f"<th class=n>Result</th><th class=n>Profit on $100</th></tr>{recent}</table></div>"
               f"<p class=sub style='margin-top:18px'><a href=\"results.html\">See all {len(allbets)} bets, and filter by won or lost&nbsp;›</a></p>")
            + "</div></section>")


def results_page(L: pd.DataFrame, stamp: str) -> str:
    """docs/results.html: the full track record."""
    from . import theme
    from .site import CSS
    body = html_section(L, full=True) or ("<section class=section style=padding-top:0><div class=wrap>"
                                          "<p class=sub>No bets recorded yet.</p></div></section>")
    body = body.replace("<h2>How the picks have done.</h2>", "", 1)
    body = body.replace("<section class=section style=padding-top:0>", "<section class=section style=padding-top:26px>", 1)
    body = body.replace("Every bet listed on this page since", "Every bet listed on the homepage since", 1)
    return f"""<!doctype html><html lang=en><head>{theme.HEAD}
{theme.meta("results.html", "Results: how every pick has done · Today's Soccer Bets",
            "Every bet listed on Today's Soccer Bets, saved at the price shown and settled from the final score.")}
<style>{CSS}</style></head><body>
{theme.nav("results")}
<section class=hero><div class=wrap>
<p class=eyebrow>Track record</p>
<h1>How every pick has done.</h1>
<p class=lede>Every bet this site has listed, and whether it won.</p>
<p class=updated>Last updated {stamp}</p>
</div></section>
{body}
{theme.footer()}
</body></html>"""


def headline(L: pd.DataFrame) -> tuple[str, str] | None:
    """Homepage tile: the record so far, e.g. ("22–4", "won–lost so far · +$149 from $100 on each")."""
    if not len(L):
        return None
    g = L[L["result"].isin(["won", "lost", "push", "half won", "half lost"])]
    if not len(g):
        return None
    w, lo = int(g["result"].isin(["won", "half won"]).sum()), int(g["result"].isin(["lost", "half lost"]).sum())
    return f"{w}–{lo}", f"picks won–lost so far\n{_usd(g['profit'].sum())} from $100 on each"
