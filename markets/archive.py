"""Keep every morning's match-result odds, so sportsbooks and prediction markets can later be compared on accuracy.

Each run appends one row per match and site to data/odds_history.csv: the time the odds were downloaded, the
match, and the site's decimal odds for home, draw and away (prediction markets after their trading fee). Nothing
is overwritten, and the file is committed by the daily job.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "data" / "odds_history.csv"
COLS = ["fetched_at", "id", "league", "kickoff", "home", "away", "site", "h", "d", "a"]


def append(t: pd.DataFrame, now: pd.Timestamp, path: Path = PATH) -> int:
    """Add today's odds (one row per match and site, from usbooks.to_table). Skips a second run on the same
    morning's download, so re-running the job doesn't double-count. Returns the number of rows added."""
    if t is None or not len(t):
        return 0
    new = t.assign(fetched_at=now.isoformat(timespec="minutes"))[COLS].copy()
    for c in ("h", "d", "a"):
        new[c] = new[c].astype(float).round(4)
    if path.exists():
        old = pd.read_csv(path, usecols=["fetched_at", "id", "site", "h", "d", "a"])
        last = old[old["fetched_at"] == old["fetched_at"].max()]
        if len(last) == len(new) and set(zip(last["id"], last["site"])) == set(zip(new["id"], new["site"])) \
                and (last.sort_values(["id", "site"])[["h", "d", "a"]].to_numpy()
                     == new.sort_values(["id", "site"])[["h", "d", "a"]].to_numpy()).all():
            return 0     # same odds as the last saved run
        new.to_csv(path, mode="a", header=False, index=False)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        new.to_csv(path, index=False)
    return len(new)
