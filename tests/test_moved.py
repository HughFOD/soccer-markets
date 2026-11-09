import numpy as np
import pandas as pd

from markets import site, track


def _ledger():
    row = {c: np.nan for c in track.COLS}
    return pd.DataFrame([
        {**row, "key": "a|result|h|", "flagged_at": "2026-11-03T05:30:00-05:00",
         "kickoff": "2026-11-20T14:30:00-05:00", "odds": 1.1, "result": ""},
        {**row, "key": "b|result|h|", "flagged_at": "2026-11-09T05:18:00-05:00",
         "kickoff": "2026-11-20T14:30:00-05:00", "odds": 2.0, "result": ""},
    ])


def test_listed_only_bets_from_earlier_days():
    now = pd.Timestamp("2026-11-09 05:20", tz="America/New_York")
    assert set(track.listed(_ledger(), now)) == {"a|result|h|"}


def test_moved_toward_and_away():
    when = pd.Timestamp("2026-11-03", tz="America/New_York")
    toward = site.moved_html({"listed": (when, 1.1), "dec": 1.093})
    away = site.moved_html({"listed": (when, 1.909), "dec": 1.926})
    assert "Listed Nov 3 at <b>−1000</b>" in toward and "toward this pick" in toward
    assert "away from this pick" in away


def test_no_line_when_unchanged_or_new():
    when = pd.Timestamp("2026-11-03", tz="America/New_York")
    assert site.moved_html({"listed": (when, 2.0), "dec": 2.0}) == ""
    assert site.moved_html({"dec": 2.0}) == ""
