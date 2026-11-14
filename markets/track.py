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



def listed(L: pd.DataFrame, now: pd.Timestamp) -> dict:
    """Bets first listed before today that haven't kicked off: key -> (date listed, decimal odds then)."""
    if not len(L):
        return {}
    ET = "America/New_York"
    today = now.tz_convert(ET).normalize()
    fl = pd.to_datetime(L["flagged_at"], utc=True).dt.tz_convert(ET)
    ko = pd.to_datetime(L["kickoff"], utc=True)
    keep = (fl < today) & (ko > now) & (L["result"] == "")
    return {L.at[i, "key"]: (fl[i], float(L.at[i, "odds"])) for i in L.index[keep]}

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
    x = round(float(x))
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
    pbar = float((1 / g["odds"].astype(float)).mean())
    tiles = (f"<div class=stats><div class=stat><div class=v>{w}–{lo}{f'–{pu}' if pu else ''}</div><div class=l>won–lost{'–push' if pu else ''}</div></div>"
             f"<div class=stat><div class=v>{_usd(profit)}</div><div class=l>profit from $100 on each ({100 * profit / (100 * n):+.1f}%)</div></div>"
             f"<div class=stat><div class=v>{100 * g['edge'].mean():+.1f}%</div><div class=l>expected return when listed</div></div>"
             # average odds via the average chance they imply (averaging American odds directly is meaningless)
             f"<div class=stat><div class=v>{american(1 / pbar).replace('-', '−')}</div><div class=l>average odds, "
             f"{'mostly favorites' if pbar > 0.5 else 'mostly underdogs'} ({100 * pbar:.0f}% chance on average)</div></div></div>")
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
          "var big=shown>PAGE;more.hidden=n<=PAGE;more.textContent=big?'Show fewer':'Show all '+n+' bets';"
          "cnt.textContent=n?'Showing '+Math.min(n,shown)+' of '+n+' bets':'No bets match these filters.'}"
          "document.querySelectorAll('.rfilt').forEach(function(b){b.addEventListener('click',function(){"
          "document.querySelectorAll('.rfilt').forEach(function(x){x.setAttribute('aria-pressed',x===b?'true':'false')});"
          "f=b.dataset.f;shown=PAGE;apply()})});"
          "lg.addEventListener('change',function(){shown=PAGE;apply()});st.addEventListener('change',function(){shown=PAGE;apply()});"
          "more.addEventListener('click',function(){if(shown>PAGE){shown=PAGE;apply();"
          "document.getElementById('rall').scrollIntoView({behavior:'smooth'})}else{shown=1e9;apply()}});apply()})()</script>")
    other = int(L["result"].isin(["not graded", "no stats found"]).sum())
    note = (" Player bets, and corner or card bets outside the six leagues (Premier League, Championship, La Liga, "
            "Bundesliga, Serie A, Ligue 1), aren't counted, because there's no free record of how they ended "
            f"({other} bet{'' if other == 1 else 's'} so far)." if other else "")
    return (f"<section class=section style=padding-top:0><div class=wrap><h2>How the picks have done.</h2><p class=sub>{intro}</p>"
            f"{tiles}"
            f"<p class=note>Wins and losses swing a lot over a few dozen bets, so the profit figure means little until there are "
            f"several hundred.{note}</p>"
            + (f"<h3 class=tally id=rall>Every settled bet</h3>{filt}"
               f"<div class=tablewrap><table class=rec><tr><th>Date</th><th>Bet</th><th>Site</th><th class=n>Odds</th><th class=n>Result</th>"
               f"<th class=n>Profit on $100</th></tr>{rows}</table></div>"
               f"<p class=rcount id=rcount></p><button class=rmore id=rmore hidden>Show more</button>{js}"
               + "<div class=chart-wrap style='margin:34px 0 6px'>" + profit_chart(g) + "</div>" if full else
               f"<h3 class=tally>Latest results</h3><div class=tablewrap><table class=rec><tr><th>Date</th><th>Bet</th><th>Site</th><th class=n>Odds</th>"
               f"<th class=n>Result</th><th class=n>Profit on $100</th></tr>{recent}</table></div>"
               f"<p class=sub style='margin-top:18px'><a href=\"results.html\">See all {len(allbets)} bets, and filter by won or lost&nbsp;›</a></p>")
            + "</div></section>")


def profit_chart(g: pd.DataFrame) -> str:
    """Running profit from $100 on every settled bet, against the profit the odds said to expect when listed."""
    from . import viz
    g = g.sort_values("kickoff")
    if len(g) < 5:
        return ""
    ko = pd.to_datetime(g["kickoff"], utc=True).dt.tz_convert("America/New_York")
    actual = g["profit"].astype(float).cumsum().round(2).tolist()
    expected = (100 * g["edge"].astype(float)).cumsum().round(2).tolist()
    days = [f"{d:%b %-d}" for d in ko]
    ticks = [d if i == 0 or d != days[i - 1] else "" for i, d in enumerate(days)]
    n = len(g)
    return viz.chart("profit", "Running profit, bet by bet",
                     "Blue: actual profit from $100 on each settled bet, in kick-off order. "
                     "Orange: expected profit, based on the odds when each bet was listed.",
                     {"type": "line", "x": [str(i + 1) for i in range(n)], "ticks": ticks, "fmt": "usd", "zero": True,
                      "series": [{"name": f"actual {actual[-1]:+,.0f}".replace("+", "+$").replace("-", "−$"), "values": actual, "color": "a"},
                                 {"name": f"expected {expected[-1]:+,.0f}".replace("+", "+$").replace("-", "−$"), "values": expected, "color": "b"}]},
                     viz._table(["After bet", "Actual profit", "Expected profit"],
                                [[f"{i + 1} ({days[i]})", f"{actual[i]:+,.0f}", f"{expected[i]:+,.0f}"] for i in range(n)][::-1]))


BREAKDOWN_CSS = (".bt{width:100%;border-collapse:collapse;font-size:14px;margin:6px 0 18px}"
                 ".bt th,.bt td{padding:7px 8px;border-bottom:1px solid var(--hair);text-align:left}"
                 ".bt .num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}"
                 ".bt th{font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:var(--ink2)}"
                 ".bt .pos{color:var(--good)}.bt .neg{color:var(--bad,#c5221f)}.bt .muted{color:var(--muted)}"
                 ".bth{margin:16px 0 4px;font-size:16px}.tw{overflow-x:auto}.bt.odds td:first-child .muted{display:block;font-size:12px}"
                 "@media (max-width:600px){.bt{font-size:13px}.bt th,.bt td{padding:7px 6px}.bt th{font-size:11px;white-space:normal}"
                 ".bt th:nth-child(3),.bt td:nth-child(3){display:none}.bt td .muted{display:block;font-size:12px}.bt .num{white-space:normal}}")
SETTLED = ["won", "lost", "push", "half won", "half lost"]


def bet_type(kind: str) -> str:
    if kind == "result":
        return "Match result"
    if kind in ("totals", "alternate_totals", "alternate_team_totals"):
        return "Total goals"
    if kind in ("spreads", "alternate_spreads"):
        return "Goal handicap"
    if "corner" in kind:
        return "Corners"
    if "card" in kind:
        return "Cards"
    if kind == "draw_no_bet":
        return "Draw no bet"
    return "Other"


def breakdown_html(L: pd.DataFrame, min_n: int = 5) -> str:
    """Results page: settled bets by the site that paid the best price and by kind of bet, with each
    group's return per $100 bet and its 95% range (bootstrap), so small groups aren't over-read."""
    from .efficiency import mean_ci
    g = L[L["result"].isin(SETTLED)].copy()
    if len(g) < 10:
        return ""
    g["site"] = g["sites"].astype(str).str.split(", ").str[0]
    g["type"] = g["kind"].astype(str).map(bet_type)

    def table(col, head):
        rows = []
        for name, x in sorted(g.groupby(col), key=lambda kv: -len(kv[1])):
            w = int(x["result"].isin(["won", "half won"]).sum()); lo = int(x["result"].isin(["lost", "half lost"]).sum())
            if len(x) >= min_n and (w == 0 or lo == 0):
                ret = f"{_usd(x['profit'].mean())} <span class=muted>(no {'losses' if lo == 0 else 'wins'} yet)</span>"
            elif len(x) >= min_n:
                est, a, b = mean_ci(x["profit"].to_numpy(float))
                ret = f"{_usd(est)} <span class=muted>({_usd(a)} to {_usd(b)})</span>"
            else:
                ret = "<span class=muted>too few bets</span>"
            cls = "pos" if x["profit"].sum() >= 0.5 else "neg" if x["profit"].sum() <= -0.5 else ""
            rows.append(f"<tr><td>{html.escape(str(name))}</td><td class=num>{len(x)}</td><td class=num>{w}–{lo}</td>"
                        f"<td class='num {cls}'>{_usd(x['profit'].sum())}</td><td class=num>{ret}</td></tr>")
        return (f"<div class=tw><table class=bt><tr><th>{head}</th><th class=num>Bets</th><th class=num>Won–lost</th>"
                f"<th class=num>Profit</th><th class=num>Per $100 (95% range)</th></tr>{''.join(rows)}</table></div>")

    return (f"<section class=section><div class=wrap><h2>By site, bet type and odds.</h2>"
            f"<p class=sub>Settled bets grouped by the site that paid the best price, by kind of bet, and by the odds. The range shows "
            f"how much each group's return could differ by luck alone: when it runs from a loss to a profit, the group "
            f"hasn't shown anything yet. Groups with fewer than {min_n} bets, or with no losses yet, get no range: a range can't account for losses that haven't happened.</p>"
            f"<h4 class=bth>By site</h4>{table('site', 'Site')}<h4 class=bth>By bet type</h4>{table('type', 'Bet type')}"
            f"{odds_table(g, min_n)}</div></section>")


ODDS_BANDS = [("Heavy favorites", "−600 or shorter", 1.0, 1 + 100 / 600),
              ("Favorites", "−599 to −200", 1 + 100 / 600, 1.5),
              ("Mild favorites", "−199 to −101", 1.5, 2.0),
              ("Underdogs", "+100 or longer", 2.0, np.inf)]


def odds_band(dec: float) -> str:
    for name, _, lo, hi in ODDS_BANDS:
        if lo < dec <= hi + 1e-9:
            return name
    return ODDS_BANDS[-1][0]


def odds_table(g: pd.DataFrame, min_n: int = 5) -> str:
    """Settled bets by odds band: wins against the wins the odds' chances expected, and the return per
    $100 against the return the edge expected. Tests the research finding that long shots do worst."""
    from .efficiency import mean_ci
    g = g.assign(band=g["odds"].astype(float).map(odds_band))
    rows = []
    for name, label, _, _ in ODDS_BANDS:
        x = g[g["band"] == name]
        if not len(x):
            continue
        w = int(x["result"].isin(["won", "half won"]).sum())
        exp_w = x["chance"].astype(float).sum()
        exp = 100 * x["edge"].astype(float).mean()
        lo = int(x["result"].isin(["lost", "half lost"]).sum())
        if len(x) < min_n:
            act = "<span class=muted>too few bets</span>"
        elif w == 0 or lo == 0:
            act = f"{_usd(x['profit'].mean())} <span class=muted>(no {'losses' if lo == 0 else 'wins'} yet)</span>"
        else:
            est, a, b = mean_ci(x["profit"].to_numpy(float))
            act = f"{_usd(est)} <span class=muted>({_usd(a)} to {_usd(b)})</span>"
        rows.append(f"<tr><td>{name}<span class=muted>{label}</span></td><td class=num>{len(x)}</td>"
                    f"<td class=num>{w} <span class=muted>expected {exp_w:.0f}</span></td>"
                    f"<td class=num>{_usd(exp)}</td><td class=num>{act}</td></tr>")
    return (f"<h4 class=bth>By odds</h4><div class=tw><table class='bt odds'><tr><th>Odds</th><th class=num>Bets</th>"
            f"<th class=num>Won</th><th class=num>Expected per $100</th><th class=num>Actual per $100 (95% range)</th></tr>"
            f"{''.join(rows)}</table></div>"
            f"<p class=note>Expected: what the odds and the consensus chance said each bet should return when it was listed. "
            f"The research found long shots are the most overpriced bets in general; this table shows over time whether that holds for these picks too.</p>")


def last_week_html(L: pd.DataFrame, now: pd.Timestamp) -> str:
    """Results page: the last seven days in one paragraph."""
    g = L[L["result"].isin(SETTLED)].copy()
    if not len(g):
        return ""
    et = "America/New_York"
    end = now.tz_convert(et).normalize()
    start = end - pd.Timedelta(days=7)
    ko = pd.to_datetime(g["kickoff"], utc=True).dt.tz_convert(et)
    w = g[(ko >= start) & (ko < end)]
    if not len(w):
        return ""
    won = int(w["result"].isin(["won", "half won"]).sum()); lost = int(w["result"].isin(["lost", "half lost"]).sum())
    best = w.loc[w["profit"].idxmax()]
    last = (end - pd.Timedelta(days=1))
    return (f"<section class=section style='padding-top:26px;padding-bottom:0'><div class=wrap><h2>Last week.</h2>"
            f"<p class=sub>{start.strftime('%b %-d')} – {last.strftime('%b %-d')}: <b>{len(w)} bets settled, {won}–{lost}</b>, "
            f"{_usd(w['profit'].sum())} at $100 a bet. Best result: {html.escape(str(best['bet']))} "
            f"({html.escape(str(best['match']))}), {_usd(best['profit'])}.</p></div></section>")


CSV_COLS = {"flagged_at": "listed_at", "kickoff": "kickoff", "league": "league", "match": "match", "bet": "bet",
            "sites": "best_site", "odds": "decimal_odds", "chance": "expected_chance", "edge": "expected_return",
            "last_checked": "last_checked", "last_value": "expected_return_at_last_check", "result": "result",
            "profit": "profit_per_100"}


def csv_export(L: pd.DataFrame, path: Path) -> None:
    """docs/track-record.csv: every bet the site has listed, for anyone to check the record themselves."""
    d = L[list(CSV_COLS)].rename(columns=CSV_COLS).sort_values("listed_at")
    d.to_csv(path, index=False, float_format="%.4f")


def held_up_html(L: pd.DataFrame, now: pd.Timestamp) -> str:
    """Results page: of the bets whose match has started and that were checked again after being listed, how many were
    still a better price than the consensus at the last check before kick-off."""
    ko = pd.to_datetime(L["kickoff"], utc=True)
    lc = pd.to_datetime(L["last_checked"], utc=True)
    fl = pd.to_datetime(L["flagged_at"], utc=True)
    d = L[(ko < now) & (lc > fl)]
    if len(d) < 5:
        return ""
    held = (d["last_value"].astype(float) > 0).mean()
    hours = float((ko - lc)[d.index].dt.total_seconds().median() / 3600)
    pct = lambda x: f"{100 * x:+.1f}%"
    return (f"<section class=section style='padding-top:26px;padding-bottom:0'><div class=wrap><h2>Did the prices hold up?</h2>"
            f"<p class=sub>Winning or losing a few dozen bets is mostly luck. A fairer test is whether each price was still better "
            f"than the consensus just before kick-off, once the news was in. This uses the last check before each match.</p>"
            f"<div class=stats><div class=stat><div class=v>{100 * held:.0f}%</div><div class=l>still a better price than the "
            f"consensus at the last check ({len(d)} bets)</div></div>"
            f"<div class=stat><div class=v>{pct(d['edge'].astype(float).mean())}</div><div class=l>expected return when listed</div></div>"
            f"<div class=stat><div class=v>{pct(d['last_value'].astype(float).mean())}</div><div class=l>expected return at the last check</div></div>"
            f"<div class=stat><div class=v>{hours:.0f} hours</div><div class=l>typical time between the last check and kick-off</div></div></div>"
            f"<p class=note>The last check is the morning update, so it isn't the exact kick-off price. Bets listed on the day of "
            f"their match aren't checked again, so they're left out.</p></div></section>")


def results_page(L: pd.DataFrame, stamp: str) -> str:
    """docs/results.html: the full track record."""
    from . import theme, viz
    from .site import CSS
    body = html_section(L, full=True) or ("<section class=section style=padding-top:0><div class=wrap>"
                                          "<p class=sub>No bets recorded yet.</p></div></section>")
    body = body.replace("<h2>How the picks have done.</h2>", "<h2>All time.</h2>", 1)
    body = body.replace("<section class=section style=padding-top:0>", "<section class=section style=padding-top:26px>", 1)
    body = body.replace("Every bet listed on this page since", "Every bet listed on the homepage since", 1)
    body = body.replace("Profit assumes $100 on each bet.",
                        "Profit assumes $100 on each bet. <a href=track-record.csv download>Download every bet (CSV)</a>.", 1)
    now = pd.Timestamp.now(tz="America/New_York")
    body = last_week_html(L, now) + body + held_up_html(L, now) + breakdown_html(L)
    return f"""<!doctype html><html lang=en><head>{theme.HEAD}
{theme.meta("results.html", "Results: how every pick has done · Today's Soccer Bets",
            "Every bet listed on Today's Soccer Bets, saved at the price shown and settled from the final score.")}
<style>{CSS}{viz.CSS}{BREAKDOWN_CSS}</style></head><body>
{theme.nav("results")}
<section class=hero><div class=wrap>
<p class=eyebrow>Track record</p>
<h1>How every pick has done.</h1>
<p class=lede>Every bet this site has listed, and whether it won.</p>
<p class=updated>Last updated {stamp}</p>
</div></section>
{body}
{theme.footer()}
<script>{viz.JS}</script>
</body></html>"""


def headline(L: pd.DataFrame) -> tuple[str, str] | None:
    """Homepage tile: the record so far, e.g. ("22–4", "won–lost so far · +$149 from $100 on each")."""
    if not len(L):
        return None
    g = L[L["result"].isin(["won", "lost", "push", "half won", "half lost"])]
    if not len(g):
        return None
    w, lo = int(g["result"].isin(["won", "half won"]).sum()), int(g["result"].isin(["lost", "half lost"]).sum())
    return f"{w}–{lo}", f"won–lost so far\n{_usd(g['profit'].sum())} profit at $100 a bet"
