from markets.usbooks import same_site


def test_polymarket_us_counts_as_polymarket():
    ev = {"bookmakers": [{"key": "kalshi"}, {"key": "polymarket", "markets": ["intl"]},
                         {"key": "polymarket_us", "markets": ["us"]}]}
    out = same_site(ev)["bookmakers"]
    assert [b["key"] for b in out] == ["kalshi", "polymarket"]
    assert out[1]["markets"] == ["us"]          # the US exchange's odds are the ones kept


def test_unchanged_without_alias():
    ev = {"bookmakers": [{"key": "fanduel"}, {"key": "polymarket"}]}
    assert same_site(ev) == ev
