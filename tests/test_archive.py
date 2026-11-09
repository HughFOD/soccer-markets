import pandas as pd

from markets import archive


def _t(h=2.0):
    return pd.DataFrame([{"id": "x", "league": "EPL", "kickoff": "2026-11-20T15:00:00Z", "home": "A", "away": "B",
                          "site": "fanduel", "h": h, "d": 3.4, "a": 3.9}])


def test_appends_and_skips_repeat(tmp_path):
    p = tmp_path / "h.csv"
    now = pd.Timestamp("2026-11-10 05:20", tz="America/New_York")
    assert archive.append(_t(), now, p) == 1
    assert archive.append(_t(), now + pd.Timedelta(hours=1), p) == 0      # same odds again: not saved twice
    assert archive.append(_t(2.1), now + pd.Timedelta(days=1), p) == 1
    d = pd.read_csv(p)
    assert len(d) == 2 and list(d.columns) == archive.COLS
