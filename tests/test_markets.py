"""Checks on the pieces the conclusions depend on."""
import numpy as np
import pandas as pd

from markets import efficiency as ef, margin, model


def test_margin_methods_return_probabilities():
    odds = np.array([[1.5, 4.2, 6.5], [2.6, 3.3, 2.9], [1.1, 9.0, 21.0]])
    for f in margin.METHODS.values():
        P = f(odds)
        assert np.allclose(P.sum(1), 1)
        assert (P > 0).all()


def test_power_and_shin_take_more_margin_off_long_shots():
    odds = np.array([[1.3, 5.5, 11.0]])
    prop, pw, sh = margin.proportional(odds), margin.power(odds), margin.shin(odds)
    assert pw[0, 0] > prop[0, 0] and pw[0, 2] < prop[0, 2]
    assert sh[0, 0] > prop[0, 0] and sh[0, 2] < prop[0, 2]


def test_calibrated_forecasts_have_slope_one():
    rng = np.random.default_rng(1)
    P = rng.dirichlet([4, 2.5, 3], size=20000)
    Y = np.array([rng.multinomial(1, p) for p in P], dtype=float)
    s = ef.calibration_slope(P, Y, n_boot=50)
    assert abs(s["slope"] - 1) < 0.06


def test_fair_odds_return_zero_and_margin_loses():
    rng = np.random.default_rng(2)
    P = rng.dirichlet([4, 2.5, 3], size=30000)
    Y = np.array([rng.multinomial(1, p) for p in P], dtype=float)
    assert abs(ef.flat_return(1 / P, Y)["return"]) < 0.03
    assert ef.flat_return(1 / (P * 1.06), Y)["return"] < -0.03


def _toy_league(n_weeks=80, seed=3):
    rng = np.random.default_rng(seed)
    teams = [f"T{i}" for i in range(8)]
    strength = dict(zip(teams, np.linspace(-0.4, 0.4, 8)))
    rows, day = [], pd.Timestamp("2015-08-01")
    for w in range(n_weeks):
        order = rng.permutation(teams)
        for h, a in zip(order[::2], order[1::2]):
            hg = rng.poisson(np.exp(0.3 + strength[h] - strength[a]))
            ag = rng.poisson(np.exp(0.1 + strength[a] - strength[h]))
            rows.append({"date": day + pd.Timedelta(days=7 * w), "league": "X", "home": h, "away": a, "hg": hg, "ag": ag})
    return pd.DataFrame(rows), strength


def test_walk_forward_never_sees_the_future():
    m, _ = _toy_league()
    w = model.walk_forward(m, min_history_days=120)
    has = w["model_h"].notna()
    assert has.sum() > 100
    assert (w.loc[has, "model_fit_end"] < m.loc[has, "date"]).all()


def test_model_recovers_who_is_stronger():
    m, strength = _toy_league(n_weeks=120)
    reg, teams = model.fit(m, m["date"].max() + pd.Timedelta(days=1), half_life=10000)
    att = dict(zip(teams, reg.coef_[: len(teams)]))
    assert np.corrcoef([att[t] for t in teams], [strength[t] for t in teams])[0, 1] > 0.8


def _synthetic_market(soft_factor, n=20000, seed=4):
    from markets import sharp  # noqa: F401
    rng = np.random.default_rng(seed)
    P = rng.dirichlet([4, 2.5, 3], size=n)
    Y = np.array([rng.multinomial(1, p) for p in P], dtype=float)
    pin = 1 / (P * 1.025)                      # Pinnacle: fair price with a 2.5% margin
    soft = soft_factor / P                     # retail price: fair price times soft_factor
    m = pd.DataFrame({"season": np.repeat(["a", "b", "c", "d"], n // 4)})
    for i, o in enumerate("hda"):
        m[f"pin_{o}"], m[f"soft_{o}"] = pin[:, i], soft[:, i]
    return m, Y


def test_generous_retail_prices_are_found_and_pay():
    from markets import sharp
    m, Y = _synthetic_market(1.05)
    rules = sharp.soft_vs_sharp_bets(m, Y)["rules"]
    r = rules[rules["edge"] == 0.0].iloc[0]
    assert r["bets"] > 0.9 * Y.size and abs(r["return"] - 0.05) < 0.03


def test_mean_retail_prices_are_not_bet():
    from markets import sharp
    m, Y = _synthetic_market(0.93)
    rules = sharp.soft_vs_sharp_bets(m, Y)["rules"]
    assert rules["bets"].sum() == 0


def test_implied_rates_recover_expected_goals():
    from markets import live
    lh, la = np.array([1.6, 0.9, 2.4]), np.array([1.1, 1.3, 0.6])
    P = live.final_probs(np.zeros(3), np.zeros(3), lh, la)  # full match from 0-0
    eh, ea = live.implied_rates(P)
    assert np.allclose(eh, lh, atol=0.03) and np.allclose(ea, la, atol=0.03)


def test_within_match_test_finds_no_effect_when_there_is_none():
    """Simulate matches where the score does not change how teams play: the trailing team's
    share of second-half goals should match its expected share (ratio near 1)."""
    from markets import live
    rng = np.random.default_rng(5)
    n = 40000
    lh, la = rng.uniform(0.8, 2.2, n), rng.uniform(0.6, 1.8, n)
    h1, a1 = rng.poisson(lh * 0.45), rng.poisson(la * 0.45)
    h2, a2 = rng.poisson(lh * 0.55), rng.poisson(la * 0.55)
    d = pd.DataFrame({"ht_hg": h1, "ht_ag": a1, "sh_h": h2, "sh_a": a2, "rem_h": lh * 0.55, "rem_a": la * 0.55})
    r = live.within_match(d)
    assert r["lo"] < 1 < r["hi"]


# ---------- fair-price engine ----------

def test_pool_of_identical_books_returns_the_same_price():
    from markets import fairprice as fp
    P = np.array([[0.5, 0.3, 0.2], [0.2, 0.3, 0.5]])
    L = np.log(np.stack([P, P, np.full_like(P, np.nan)]))      # third bookmaker missing
    assert np.allclose(fp.pool(L, np.array([0.2, 0.5, 0.3])), P)


def test_weights_favour_the_bookmaker_closest_to_the_closing_price():
    from markets import fairprice as fp
    rng = np.random.default_rng(6)
    T = rng.dirichlet([4, 2.5, 3], size=3000)
    noisy = lambda s: (lambda q: q / q.sum(1, keepdims=True))(T * np.exp(rng.normal(0, s, T.shape)))
    Pb = np.stack([noisy(0.03), noisy(0.25)])                  # a sharp and a sloppy bookmaker
    w = fp.fit_weights(Pb, T)
    assert w[0] > 3 * w[1]


def _toy_market(generous):
    """Matches priced by a sharp book (fair, 2.5% margin) and a retail book offering `generous` x fair odds;
    the closing price equals the fair price."""
    rng = np.random.default_rng(7)
    n = 4000
    T = rng.dirichlet([4, 2.5, 3], size=n)
    Y = np.array([rng.multinomial(1, p) for p in T], dtype=float)
    m = pd.DataFrame({"season": "s", "date": pd.Timestamp("2020-01-01") + pd.to_timedelta(np.arange(n) // 10, "D")})
    for i, o in enumerate("hda"):
        m[f"bk_PS_{o}"] = 1 / (T[:, i] * 1.025)
        m[f"bk_XX_{o}"] = generous / T[:, i]
        m[f"pinc_{o}"] = 1 / T[:, i]
    return m, Y, T


def test_backtest_clv_matches_a_known_edge():
    from markets import fairprice as fp
    m, Y, T = _toy_market(1.03)
    bt = fp.backtest(m, Y, T, ["PS", "XX"])
    r = bt["rules"].set_index("threshold").loc[0.02]
    assert r["bets"] == 3 * len(m) and abs(r["clv"] - 0.03) < 0.002 and r["beat_close"] == 1.0


def test_fair_prices_are_never_flagged():
    from markets import fairprice as fp
    m, Y, T = _toy_market(0.95)
    assert fp.backtest(m, Y, T, ["PS", "XX"])["rules"]["bets"].sum() == 0


def test_american_odds():
    from markets.usbooks import american
    assert american(2.5) == "+150" and american(1.5) == "-200" and american(2.0) == "+100"


def test_consensus_comparison_flags_the_generous_site(monkeypatch):
    from markets import usbooks
    monkeypatch.setattr(usbooks, "FEE_RATES", {})   # tests the consensus logic alone; fees have their own tests
    ev = lambda books: {"id": "e1", "commence_time": "2026-10-31T15:00:00Z", "home_team": "A", "away_team": "B",
                        "bookmakers": [{"key": k, "title": k, "markets": [{"key": "h2h", "outcomes": [
                            {"name": "A", "price": h}, {"name": "B", "price": a}, {"name": "Draw", "price": d}]}]}
                                       for k, h, d, a in books]}
    raw = {"soccer_epl|us": [ev([("draftkings", 2.0, 3.4, 3.6), ("fanduel", 2.0, 3.4, 3.6), ("bovada", 9.0, 9.0, 9.0)])],
           "soccer_epl|us_ex": [ev([("kalshi", 2.08, 3.5, 3.8), ("polymarket", 2.2, 3.4, 3.6)])]}
    t = usbooks.to_table(raw)
    assert "bovada" not in set(t["site"])                     # only the listed US sites count
    M, quotes = usbooks.price(t)
    r = M.iloc[0]
    assert r["best_site_h"] == "Polymarket" and "Home" in r["flag"]
    board = usbooks.scoreboard(quotes, t)
    assert set(board.nlargest(2, "avg_edge")["name"]) == {"Kalshi", "Polymarket"}   # lower cuts, so they pay more
    assert list(board["site"]) == [k for k in usbooks.SITES if k in set(board["site"])]    # listed in market-share order


def test_daily_picks_rank_only_bets_that_beat_the_fair_price(monkeypatch):
    import pandas as pd
    from markets import site, usbooks
    monkeypatch.setattr(usbooks, "FEE_RATES", {})   # tests the ranking alone; fees have their own tests
    ko = "2026-10-31T15:00:00Z"
    ev = lambda mid, books: {"id": mid, "commence_time": ko, "home_team": "A" + mid, "away_team": "B" + mid,
                             "bookmakers": [{"key": k, "title": k, "markets": [{"key": "h2h", "outcomes": [
                                 {"name": "A" + mid, "price": h}, {"name": "B" + mid, "price": a}, {"name": "Draw", "price": d}]}]}
                                 for k, (h, d, a) in books.items()]}
    fair = {"fanduel": (2.40, 3.30, 3.00), "draftkings": (2.40, 3.30, 3.00), "betmgm": (2.40, 3.30, 3.00)}
    raw = {"soccer_epl|us": [ev("1", {**fair, "kalshi": (2.70, 3.30, 3.00)}),     # big edge on the home win
                             ev("2", {**fair, "kalshi": (2.60, 3.30, 3.00)}),     # smaller edge
                             ev("3", fair)]}                                       # nothing beats fair
    M, q = usbooks.price(usbooks.to_table(raw))
    days = site.daily_picks(M, q, now=pd.Timestamp("2026-10-31T08:00", tz=site.ET))
    assert [lab for lab, _ in days] == ["Today"]
    bets = days[0][1]
    assert [b["bet"] for b in bets[:2]] == ["A1 to win", "A2 to win"]           # ranked by value
    assert all(b["edge"] > site.MIN_EDGE for b in bets) and bets[0]["sites"] == ["Kalshi"]
    assert site.daily_picks(M, q, now=pd.Timestamp("2026-10-31T12:00", tz=site.ET)) == [("Today", [])]  # kicked off


def _totals_raw(lines, mid="t1", ko="2026-10-31T15:00:00Z"):
    """lines: {site: (point, over, under)}"""
    return {"soccer_epl|us|totals": [{"id": mid, "commence_time": ko, "home_team": "A", "away_team": "B",
             "bookmakers": [{"key": k, "title": k, "markets": [{"key": "totals", "outcomes": [
                 {"name": "Over", "price": o, "point": p}, {"name": "Under", "price": u, "point": p}]}]}
                 for k, (p, o, u) in lines.items()]}]}


def test_goals_totals_are_priced_like_match_results():
    from markets import usbooks
    raw = _totals_raw({"fanduel": (2.5, 1.90, 1.90), "draftkings": (2.5, 1.90, 1.90),
                       "betmgm": (2.5, 2.10, 1.75), "kalshi": (3.5, 3.0, 1.35)})   # kalshi on another line: ignored
    t = usbooks.totals_table(raw)
    assert set(t["point"]) == {2.5, 3.5} and len(t) == 4
    G = usbooks.price_totals(t)
    assert set(G["point"]) == {2.5}                                  # 3.5 has one site, below min_sites
    over = G[(G["side"] == "Over") & G["best"]].iloc[0]
    assert over["site"] == "betmgm" and over["edge"] > 0               # 2.10 beats the pooled chance
    assert abs(G.groupby("site")["chance"].first().sum() / 3 - G[G["side"] == "Over"]["chance"].iloc[0]) < 1
    assert usbooks.to_table(raw).empty                                 # totals never leak into match results


def test_daily_picks_include_goals_bets():
    import pandas as pd
    from markets import site, usbooks
    G = usbooks.price_totals(usbooks.totals_table(_totals_raw(
        {"fanduel": (2.5, 1.90, 1.90), "draftkings": (2.5, 1.90, 1.90), "betmgm": (2.5, 2.10, 1.75)})))
    M = pd.DataFrame([{"id": "t1"}])
    q = pd.DataFrame(columns=["id", "site", "result", "odds", "edge", "best"])
    days = site.daily_picks(M, q, now=pd.Timestamp("2026-10-31T08:00", tz=site.ET), totals=G)
    bets = days[0][1]
    assert bets[0]["bet"] == "Over 2.5 goals" and bets[0]["sites"] == ["BetMGM"]


def test_goals_are_fetched_only_for_leagues_playing_today():
    import pandas as pd
    from markets import usbooks
    ev = lambda ko: [{"id": ko, "commence_time": ko, "home_team": "A", "away_team": "B", "bookmakers": []}]
    raw = {"soccer_epl|us": ev("2026-10-31T15:00:00Z"), "soccer_epl|us_ex": ev("2026-10-31T15:00:00Z"),
           "soccer_spain_la_liga|us": ev("2026-11-03T20:00:00Z"), "soccer_italy_serie_a|us": []}
    now = pd.Timestamp("2026-10-31T06:00", tz="America/New_York")
    assert usbooks.soon_sports(raw, now) == ["soccer_epl"]                 # today only by default
    assert usbooks.soon_sports(raw, now - pd.Timedelta(days=1)) == []       # the day before: nothing today


def _extras_event():
    def bk(key, markets):
        return {"key": key, "markets": [{"key": k, "outcomes": o} for k, o in markets.items()]}
    corners = lambda o, u: [{"name": "Over", "point": 9.5, "price": o}, {"name": "Under", "point": 9.5, "price": u}]
    btts = lambda y, n: [{"name": "Yes", "price": y}, {"name": "No", "price": n}]
    scorer = lambda p: [{"name": "Yes", "description": "Bukayo Saka", "price": p}]
    return {"e1": {"id": "e1", "home_team": "Arsenal", "away_team": "Chelsea", "bookmakers": [
        bk("fanduel", {"alternate_totals_corners": corners(1.90, 1.90), "btts": btts(1.80, 2.00),
                       "player_goal_scorer_anytime": scorer(3.0)}),
        bk("draftkings", {"alternate_totals_corners": corners(1.95, 1.85), "btts": btts(1.85, 1.95),
                          "player_goal_scorer_anytime": scorer(3.4)}),
        bk("bovada", {"alternate_totals_corners": corners(5.0, 5.0)}),        # not a listed site
    ]}}


def test_extra_markets_are_priced_where_both_sides_are_quoted():
    from markets import extras
    from markets import usbooks
    t = extras.table(_extras_event(), usbooks.SITES)
    assert set(t["site"]) == {"fanduel", "draftkings"}
    X = extras.price(t)
    over = X[(X["market"] == "alternate_totals_corners") & (X["outcome"] == "Over")]
    assert over["label"].iloc[0] == "Over 9.5 corners"
    assert over["chance"].notna().all() and np.isclose(over["chance"].iloc[0] + X[(X["market"] == "alternate_totals_corners") & (X["outcome"] == "Under")]["chance"].iloc[0], 1)
    assert over[over["site"] == "draftkings"]["edge"].iloc[0] > over[over["site"] == "fanduel"]["edge"].iloc[0]   # better price, better return
    s = X[X["market"] == "player_goal_scorer_anytime"]
    assert s["chance"].isna().all() and s["label"].iloc[0] == "Bukayo Saka to score"                   # one-sided: odds only
    assert s[s["best"]]["site"].tolist() == ["draftkings"]


def test_extras_only_fetched_for_matches_today():
    from markets import extras
    now = pd.Timestamp("2026-10-31T12:00Z")
    raw = {"soccer_epl|us": [{"id": "a", "commence_time": "2026-10-31T15:00:00Z"}, {"id": "b", "commence_time": "2026-11-02T15:00:00Z"}],
           "soccer_epl|us_ex": [{"id": "a", "commence_time": "2026-10-31T15:00:00Z"}],
           "soccer_epl|us,us_ex|totals": [{"id": "c", "commence_time": "2026-10-31T13:00:00Z"}]}
    assert extras.due(raw, now) == [("soccer_epl", "a")]


def test_prediction_market_fees_lower_the_odds():
    from markets.usbooks import after_fees
    # Kalshi at 50 cents: fee 0.07 x 0.5 x 0.5 = 1.75 cents, so $1 costs 51.75 cents.
    assert abs(after_fees("kalshi", 2.0) - 1 / 0.5175) < 1e-9
    assert abs(after_fees("polymarket", 2.0) - 1 / 0.5125) < 1e-9
    assert after_fees("fanduel", 2.0) == 2.0            # sportsbooks: the cut is already in the odds
    assert after_fees("kalshi", 10.0) < 10.0 and after_fees("kalshi", 1.1) < 1.1


def test_prediction_market_edge_shrinks_once_fees_are_paid():
    """The same prediction-market quote is worth less to a bettor once its fee is counted."""
    from markets import usbooks
    ev = {"id": "m1", "home_team": "A", "away_team": "B", "commence_time": "2026-11-01T15:00:00Z", "bookmakers": []}
    for key, (h, d, a) in {"fanduel": (2.3, 3.2, 3.0), "draftkings": (2.3, 3.25, 2.95),
                           "betmgm": (2.35, 3.2, 2.95), "kalshi": (2.45, 3.45, 3.15)}.items():
        ev["bookmakers"].append({"key": key, "markets": [{"key": "h2h", "outcomes": [
            {"name": "A", "price": h}, {"name": "Draw", "price": d}, {"name": "B", "price": a}]}]})
    raw = {"soccer_epl|us": [ev]}
    usbooks.FEE_RATES, saved = {}, dict(usbooks.FEE_RATES)
    try:
        _, q_free = usbooks.price(usbooks.to_table(raw))
    finally:
        usbooks.FEE_RATES = saved
    _, q_fee = usbooks.price(usbooks.to_table(raw))
    kal_free = q_free[q_free.site == "kalshi"].edge.max()
    kal_fee = q_fee[q_fee.site == "kalshi"].edge.max()
    assert kal_fee < kal_free - 0.02


def test_impossible_odds_are_skipped_not_fatal():
    """Odds of 1.0 or less (a "certain" result) once crashed the daily update; they are now left out."""
    odds = np.array([[1.0, 15.0], [1.001, 30.0], [1.9, 1.95]])
    for f in (margin.power, margin.shin):   # the solvers that used to crash
        P = f(odds)
        assert np.isnan(P[0]).all()
        assert np.isfinite(P[2]).all() and np.isclose(P[2].sum(), 1)
    P = margin.power(odds)
    assert np.isfinite(P[1]).all() and np.isclose(P[1].sum(), 1)


def _row(kind, outcome, point=None, home="A", away="B"):
    return {"kind": kind, "outcome": outcome, "point": point if point is not None else float("nan"),
            "home": home, "away": away}


def test_track_record_settles_from_the_final_score():
    from markets import track
    P = lambda row, hg, ag, odds=2.0: track.profit_and_label(track.settle(row, hg, ag), odds)
    assert P(_row("result", "h"), 2, 1) == (100.0, "won")
    assert P(_row("result", "d"), 2, 1) == (-100.0, "lost")
    assert P(_row("totals", "Over", 2.5), 2, 1) == (100.0, "won")
    assert P(_row("alternate_totals", "Under", 3.0), 2, 1) == (0.0, "push")
    assert P(_row("alternate_spreads", "A", -1.5), 2, 1) == (-100.0, "lost")
    assert P(_row("alternate_spreads", "B", 1.5), 2, 1) == (100.0, "won")
    assert P(_row("alternate_spreads", "A", -0.25), 1, 1) == (-50.0, "half lost")   # half push, half loss
    assert P(_row("alternate_totals", "Over", 2.75), 3, 0) == (50.0, "half won")    # half win, half push
    assert P(_row("btts", "Yes"), 1, 1) == (100.0, "won")
    assert P(_row("draw_no_bet", "B"), 1, 1) == (0.0, "push")
    assert track.settle(_row("alternate_totals_corners", "Over", 9.5), 1, 0) is None


def test_track_record_saves_once_rechecks_and_grades(tmp_path, monkeypatch):
    import pandas as pd
    from markets import track
    monkeypatch.setattr(track, "LEDGER", tmp_path / "track_record.csv")
    ko = pd.Timestamp("2026-11-01T15:00", tz="UTC")
    bet = {"id": "m1", "kind": "result", "outcome": "h", "point": float("nan"), "match": "A v B", "ko": ko,
           "league": "Premier League", "bet": "A to win", "sites": ["FanDuel"], "n_sites": 5, "dec": 2.2,
           "chance": 0.48, "edge": 0.056}
    corner = {**bet, "kind": "alternate_totals_corners", "outcome": "Over", "point": 9.5, "bet": "Over 9.5 corners"}
    t0 = pd.Timestamp("2026-10-31T10:00", tz="UTC")
    L = track.record(track.load(), [("Tomorrow", [bet, corner])], t0)
    L = track.record(L, [("Tomorrow", [bet])], t0 + pd.Timedelta(hours=1))          # already saved: not duplicated
    assert len(L) == 2
    L = track.update(L, [{**bet, "chance": 0.44}], pd.Timestamp("2026-11-01T10:00", tz="UTC"))
    r = L[L["kind"] == "result"].iloc[0]
    assert abs(r["last_value"] - (0.44 * 2.2 - 1)) < 1e-9                          # price no longer beats expected
    assert track.sports_needed(L, ko + pd.Timedelta(hours=3)) == ["soccer_epl"]
    L = track.grade(L, {"m1": (2, 0)}, ko + pd.Timedelta(hours=3))
    assert list(L["result"]) == ["won", "not graded"] and L["profit"].iloc[0] == 120.0
    track.save(L)
    L2 = track.load()
    assert len(L2) == 2 and "How the picks have done" in track.html_section(L2)
