"""Load football-data.co.uk match files into one tidy table.

Each file is one league-season: results plus the 1X2 (home / draw / away)
decimal odds offered by several bookmakers. Column sets change over the years,
so everything is mapped onto a fixed set of columns:

    date, season, league, home, away, hg, ag, result   (result is H, D or A)
    ht_hg, ht_ag   half-time score; h_red, a_red   red cards
    cons_{h,d,a}   consensus probability: each bookmaker's odds turned into
                   probabilities (margin removed), averaged across bookmakers
    best_{h,d,a}   best available decimal odds across bookmakers
    avg_{h,d,a}    average decimal odds across bookmakers
    pin_{h,d,a}    Pinnacle odds (a low-margin bookmaker; from 2012)
    pinc_{h,d,a}   Pinnacle closing odds, just before kick-off (from 2015/16)
    soft_{h,d,a}   best odds among retail ("soft") bookmakers, i.e. excluding Pinnacle and the Betfair exchange
    n_books        how many bookmakers priced the match
"""
from __future__ import annotations

import io
import re
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

OUTCOMES = ("H", "D", "A")
# bookmaker prefixes used by football-data.co.uk over the years
BOOKS = ("B365", "BW", "IW", "LB", "PS", "WH", "SJ", "VC", "GB", "BS", "SB", "SY", "SO", "BF", "1XB", "CL", "BV",
         "BFD", "BMGM", "PP", "SKB", "BFE")

# low-margin bookmakers / exchanges that take large bets; everything else is a "soft" (retail) bookmaker
SHARP = ("PS", "BF", "BFE")  # Pinnacle, Betfair and the Betfair Exchange

LEAGUES = {  # football-data.co.uk code -> readable name
    "E0": "England Premier League", "E1": "England Championship", "SP1": "Spain La Liga",
    "D1": "Germany Bundesliga", "I1": "Italy Serie A", "F1": "France Ligue 1",
    "N1": "Netherlands Eredivisie", "P1": "Portugal Primeira Liga",
}
FILE_LEAGUE = {"Premier": "E0", "Championship": "E1"}
SEASON_RE = re.compile(r"(\d{4})-(\d{4})")


def download(dest: Path, leagues=("E0", "E1", "SP1", "D1", "I1", "F1"), first=2005, last=2026) -> list[Path]:
    """Download league-season files from football-data.co.uk (run on a normal internet connection).

    Saves as {league}_{YYYY-YYYY}.csv. Files already present are skipped,
    except the current season, which is re-downloaded because it is still growing.
    """
    dest.mkdir(parents=True, exist_ok=True)
    got = []
    for y in range(first, last + 1):
        code = f"{y % 100:02d}{(y + 1) % 100:02d}"
        for lg in leagues:
            out = dest / f"{lg}_{y}-{y + 1}.csv"
            if out.exists() and y < last:
                got.append(out)
                continue
            url = f"https://www.football-data.co.uk/mmz4281/{code}/{lg}.csv"
            try:
                with urllib.request.urlopen(url, timeout=30) as r:
                    out.write_bytes(r.read())
                got.append(out)
                print(f"  downloaded {out.name}")
            except Exception as e:  # season not published yet, or league missing that year
                print(f"  skipped {lg} {y}-{y + 1}: {e}")
    return got


def _league_and_season(path: Path) -> tuple[str, str]:
    m = SEASON_RE.search(path.stem)
    season = m.group(0) if m else "unknown"
    stem = path.stem.replace(season, "").strip("_-")
    parts = [p for p in stem.split("_") if p]
    lg = parts[-1] if parts else stem
    return FILE_LEAGUE.get(lg, lg), season


def _read(path: Path) -> pd.DataFrame:
    b = path.read_bytes()
    try:
        raw = b.decode("utf-8-sig")
    except UnicodeDecodeError:
        raw = b.decode("latin-1")
    d = pd.read_csv(io.StringIO(raw), on_bad_lines="skip", low_memory=False)
    d.columns = d.columns.astype(str).str.replace("\ufeff", "", regex=False).str.replace("ï»¿", "", regex=False).str.strip()
    d = d.loc[:, ~d.columns.str.startswith("Unnamed")]
    return d.dropna(how="all")


def _probs_from_odds(oh, od, oa) -> np.ndarray:
    """Proportional margin removal: 1/odds, rescaled to sum to 1."""
    inv = 1 / np.column_stack([oh, od, oa])
    return inv / inv.sum(axis=1, keepdims=True)


def _num(d: pd.DataFrame, col: str) -> pd.Series:
    if col not in d.columns:
        return pd.Series(np.nan, index=d.index)
    s = pd.to_numeric(d[col], errors="coerce")
    return s.where(s > 1.0)  # decimal odds are always above 1


def tidy(d: pd.DataFrame, league: str, season: str) -> pd.DataFrame:
    out = pd.DataFrame({
        "date": pd.to_datetime(d["Date"], dayfirst=True, errors="coerce", format="mixed"),
        "season": season,
        "league": d["Div"].iloc[0] if "Div" in d.columns and len(d) else league,
        "home": d["HomeTeam"] if "HomeTeam" in d.columns else d.get("HT"),
        "away": d["AwayTeam"] if "AwayTeam" in d.columns else d.get("AT"),
        "hg": pd.to_numeric(d["FTHG"], errors="coerce") if "FTHG" in d.columns else np.nan,
        "ag": pd.to_numeric(d["FTAG"], errors="coerce") if "FTAG" in d.columns else np.nan,
        "result": d["FTR"] if "FTR" in d.columns else None,
        "ht_hg": pd.to_numeric(d["HTHG"], errors="coerce") if "HTHG" in d.columns else np.nan,
        "ht_ag": pd.to_numeric(d["HTAG"], errors="coerce") if "HTAG" in d.columns else np.nan,
        "h_red": pd.to_numeric(d["HR"], errors="coerce") if "HR" in d.columns else np.nan,
        "a_red": pd.to_numeric(d["AR"], errors="coerce") if "AR" in d.columns else np.nan,
    })
    probs, odds, soft = [], [], []
    for b in BOOKS:
        oh, od, oa = (_num(d, f"{b}{o}") for o in OUTCOMES)
        if oh.isna().all():
            continue
        p = _probs_from_odds(oh, od, oa)
        probs.append(p)
        odds.append(np.column_stack([oh, od, oa]))
        if b not in SHARP:
            soft.append(odds[-1])
    with _quiet():
        soft_best = np.nanmax(np.stack(soft), axis=0) if soft else np.full((len(d), 3), np.nan)
    if probs:
        P = np.stack(probs)                      # books x matches x 3
        O = np.stack(odds)
        with np.errstate(invalid="ignore"), _quiet():
            cons = np.nanmean(P, axis=0)
            best = np.nanmax(O, axis=0)
            avg = np.nanmean(O, axis=0)
        n = np.isfinite(P[:, :, 0]).sum(axis=0)
    else:
        cons = best = avg = np.full((len(d), 3), np.nan)
        n = np.zeros(len(d), dtype=int)
    # prefer the file's own market-wide max/average columns when present (they cover more bookmakers)
    for prefix, arr in (("BbMx", best), ("Max", best), ("BbAv", avg), ("Avg", avg)):
        cols = [_num(d, f"{prefix}{o}") for o in OUTCOMES]
        if not cols[0].isna().all():
            have = np.column_stack(cols)
            arr[:] = np.where(np.isfinite(have), have, arr)
    for i, o in enumerate("hda"):
        out[f"cons_{o}"] = cons[:, i]
        out[f"best_{o}"] = best[:, i]
        out[f"avg_{o}"] = avg[:, i]
        out[f"pin_{o}"] = _num(d, f"PS{OUTCOMES[i]}").to_numpy()
        out[f"pinc_{o}"] = _num(d, f"PSC{OUTCOMES[i]}").to_numpy()
        out[f"soft_{o}"] = soft_best[:, i]
    # every bookmaker's own odds (and closing odds, where the file has them), for the fair-price engine
    for b in BOOKS:
        if _num(d, f"{b}H").isna().all():
            continue
        for i, o in enumerate("hda"):
            out[f"bk_{b}_{o}"] = _num(d, f"{b}{OUTCOMES[i]}").to_numpy()
            if f"{b}C{OUTCOMES[i]}" in d.columns:
                out[f"bkc_{b}_{o}"] = _num(d, f"{b}C{OUTCOMES[i]}").to_numpy()
    out["n_books"] = n
    return out


class _quiet:
    def __enter__(self):
        import warnings
        self._w = warnings.catch_warnings()
        self._w.__enter__()
        warnings.simplefilter("ignore", RuntimeWarning)

    def __exit__(self, *a):
        self._w.__exit__(*a)


def load(raw_dir: Path) -> pd.DataFrame:
    frames = []
    for path in sorted(Path(raw_dir).glob("*.csv")):
        lg, season = _league_and_season(path)
        d = _read(path)
        if not {"FTHG", "FTAG", "FTR"} <= set(d.columns):
            continue
        frames.append(tidy(d, lg, season))
    m = pd.concat(frames, ignore_index=True)
    m = m.dropna(subset=["date", "home", "away", "hg", "ag"])
    m = m[m["result"].isin(OUTCOMES)]
    m = m[np.isfinite(m[["cons_h", "cons_d", "cons_a"]]).all(axis=1)]
    m = m.drop_duplicates(subset=["date", "home", "away"])
    m["hg"] = m["hg"].astype(int)
    m["ag"] = m["ag"].astype(int)
    return m.sort_values(["date", "league", "home"]).reset_index(drop=True)


def outcome_matrix(m: pd.DataFrame) -> np.ndarray:
    """One-hot results, columns H, D, A."""
    return np.column_stack([(m["result"] == o).to_numpy() for o in OUTCOMES]).astype(float)


FIXTURES_URL = "https://www.football-data.co.uk/fixtures.csv"


def download_fixtures(dest: Path) -> Path:
    """This week's upcoming matches with current odds (football-data.co.uk updates it twice a week)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(FIXTURES_URL, timeout=30) as r:
        dest.write_bytes(r.read())
    return dest


def load_fixtures(path: Path, leagues: tuple[str, ...] | None = None) -> pd.DataFrame:
    """Upcoming matches in the same layout as `load`, without results."""
    d = _read(Path(path))
    f = tidy(d, "", "upcoming")
    f["league"] = d["Div"].to_numpy() if "Div" in d.columns else ""
    if "Time" in d.columns:
        f["time"] = d["Time"].to_numpy()
    f = f.dropna(subset=["date", "home", "away"])
    if leagues:
        f = f[f["league"].isin(leagues)]
    return f.sort_values(["date", "league", "home"]).reset_index(drop=True)
