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


def test_heavy_favorites_need_a_bigger_edge():
    assert abs(site.HEAVY_FAV - 1.1667) < 1e-3
    keep = lambda dec, edge: dec >= site.HEAVY_FAV or edge >= site.HEAVY_FAV_EDGE
    assert not keep(1.11, 0.011)     # -909 at +$1.10: left out
    assert keep(1.11, 0.035)         # -909 at +$3.50: listed
    assert keep(1.25, 0.005)         # -400 at +$0.50: unaffected


def test_breakdown_no_minus_zero():
    from markets import track
    assert track._usd(-0.3) == "+$0" and track._usd(-6.4) == "−$6"
