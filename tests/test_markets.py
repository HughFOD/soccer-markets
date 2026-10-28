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
