"""Run every analysis, save charts, results.json and report.md."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from . import data, efficiency as ef, margin, model

BLUE, ORANGE, AQUA, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#1baf7a", "#0b0b0b", "#52514e", "#e4e3df"
HDA = ["h", "d", "a"]
NO_CROWDS = (pd.Timestamp("2020-06-01"), pd.Timestamp("2021-05-31"))


def cols(prefix: str) -> list[str]:
    return [f"{prefix}_{o}" for o in HDA]


def _style(ax, title, xlabel, ylabel):
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=10)
    ax.set_xlabel(xlabel, color=MUTED)
    ax.set_ylabel(ylabel, color=MUTED)
    ax.grid(color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=MUTED)


def _save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ---------------- analyses ----------------

def margins_by_season(m: pd.DataFrame) -> pd.DataFrame:
    m = m.assign(avg_margin=margin.overround(m[cols("avg")].to_numpy()),
                 pin_margin=margin.overround(m[cols("pin")].to_numpy()))
    g = m.groupby("season").agg(avg_margin=("avg_margin", "median"), pin_margin=("pin_margin", "median"),
                                matches=("home", "size"))
    return g.reset_index()


def calibration(m: pd.DataFrame, Y: np.ndarray) -> dict:
    P = m[cols("cons")].to_numpy()
    table = ef.calibration_table(P, Y)
    pooled = ef.calibration_slope(P, Y)
    per = {o: ef.calibration_slope(P[:, [i]], Y[:, [i]], n_boot=300) for i, o in enumerate("HDA")}
    priced = P.mean(0)
    return {"table": table, "pooled": pooled, "per_outcome": per,
            "priced_share": dict(zip("HDA", priced)), "actual_share": dict(zip("HDA", Y.mean(0)))}


def margin_methods(m: pd.DataFrame, Y: np.ndarray) -> pd.DataFrame:
    O = m[cols("avg")].to_numpy()
    rows = []
    for name, f in margin.METHODS.items():
        P = f(O)
        ok = np.isfinite(P).all(1)
        ll = ef.log_loss(P[ok], Y[ok])
        rows.append({"method": name, "log_loss": ll.mean(), "slope": ef.calibration_slope(P[ok], Y[ok], n_boot=100)["slope"]})
    base = rows[0]["log_loss"]
    for r in rows:
        r["vs_proportional"] = r["log_loss"] - base
    return pd.DataFrame(rows)


def favourite_longshot(m: pd.DataFrame, Y: np.ndarray) -> dict:
    out = {"average": ef.returns_by_odds(m[cols("avg")].to_numpy(), Y),
           "best": ef.returns_by_odds(m[cols("best")].to_numpy(), Y)}
    pin = m[cols("pin")].notna().all(1).to_numpy()
    out["pinnacle"] = ef.returns_by_odds(m.loc[pin, cols("pin")].to_numpy(), Y[pin])
    return out


def by_outcome_returns(m: pd.DataFrame, Y: np.ndarray) -> pd.DataFrame:
    rows = []
    for src in ("avg", "best", "pin"):
        O = m[cols(src)].to_numpy()
        for i, o in enumerate(["home", "draw", "away"]):
            mask = np.zeros_like(O, dtype=bool)
            mask[:, i] = True
            rows.append({"odds": src, "outcome": o, **ef.flat_return(O, Y, mask, seed=i)})
    return pd.DataFrame(rows)


def opening_vs_closing(m: pd.DataFrame, Y: np.ndarray) -> dict | None:
    s = m[cols("pin") + cols("pinc")].notna().all(1).to_numpy()
    if s.sum() < 500:
        return None
    Oo, Oc = m.loc[s, cols("pin")].to_numpy(), m.loc[s, cols("pinc")].to_numpy()
    Po, Pc, Ys = margin.proportional(Oo), margin.proportional(Oc), Y[s]
    llo, llc = ef.log_loss(Po, Ys), ef.log_loss(Pc, Ys)
    diff = ef.mean_ci(llc - llo)
    return {"matches": int(s.sum()), "seasons": sorted(m.loc[s, "season"].unique().tolist()),
            "log_loss_open": float(llo.mean()), "log_loss_close": float(llc.mean()),
            "diff": diff, "margin_open": float(np.median(margin.overround(Oo))),
            "margin_close": float(np.median(margin.overround(Oc))),
            "moves": ef.line_moves(Po, Pc, Oo, Ys),
            "bet_all_close": ef.flat_return(Oc, Ys), "bet_all_open": ef.flat_return(Oo, Ys)}


def tune_half_life(m: pd.DataFrame, cutoff: str) -> tuple[float, dict]:
    """Choose the decay on early seasons only, so the evaluation seasons stay untouched."""
    early = m[m["date"] < pd.Timestamp(cutoff)].reset_index(drop=True)
    Y = data.outcome_matrix(early)
    scores = {}
    for hl in (90, 180, 365, 730):
        w = model.walk_forward(early, half_life=hl)
        ok = w["model_h"].notna().to_numpy()
        scores[hl] = float(ef.log_loss(w.loc[ok, ["model_h", "model_d", "model_a"]].to_numpy(), Y[ok]).mean())
    return min(scores, key=scores.get), scores


def stack_by_season(feat_seasons: pd.Series, X: np.ndarray, Y: np.ndarray, min_train: int = 2) -> np.ndarray:
    """Multinomial logistic regression, refitted for each season on earlier seasons only."""
    seasons = sorted(feat_seasons.unique())
    y = Y.argmax(1)
    P = np.full((len(X), 3), np.nan)
    for i, s in enumerate(seasons):
        if i < min_train:
            continue
        tr = feat_seasons.isin(seasons[:i]).to_numpy()
        te = (feat_seasons == s).to_numpy()
        lr = LogisticRegression(C=100, max_iter=2000).fit(X[tr], y[tr])
        P[te] = lr.predict_proba(X[te])
    return P


def model_vs_market(m: pd.DataFrame, Y: np.ndarray, half_life: float, eval_from: str) -> dict:
    w = model.walk_forward(m, half_life=half_life)
    has = w["model_h"].notna().to_numpy()
    Pm_all = w[["model_h", "model_d", "model_a"]].to_numpy()
    Pc_all = m[cols("cons")].to_numpy()
    lg = lambda P: np.log(np.clip(P, 1e-9, 1))
    sub = m[has].reset_index(drop=True)
    Pm, Pc, Ys = Pm_all[has], Pc_all[has], Y[has]
    X_both = np.hstack([lg(Pm), lg(Pc)])
    P_mkt_recal = stack_by_season(sub["season"], lg(Pc), Ys)
    P_both = stack_by_season(sub["season"], X_both, Ys)
    ev = (sub["date"] >= pd.Timestamp(eval_from)).to_numpy() & np.isfinite(P_both).all(1) & np.isfinite(P_mkt_recal).all(1)
    Ye = Ys[ev]
    scores = {}
    for name, P in (("uniform", np.full_like(Pc[ev], 1 / 3)), ("model", Pm[ev]), ("market", Pc[ev]),
                    ("market_recalibrated", P_mkt_recal[ev]), ("market_plus_model", P_both[ev])):
        scores[name] = {"log_loss": float(ef.log_loss(P, Ye).mean()), "rps": float(ef.rps(P, Ye).mean()),
                        "brier": float(ef.brier(P, Ye).mean())}
    gain = ef.mean_ci(ef.log_loss(P_mkt_recal[ev], Ye) - ef.log_loss(P_both[ev], Ye))
    gain_raw = ef.mean_ci(ef.log_loss(Pc[ev], Ye) - ef.log_loss(Pm[ev], Ye))

    # value betting: bet 1 when a forecast says the odds are generous by more than `edge`
    e = sub[ev].reset_index(drop=True)
    bets = {}
    for fname, P in (("model", Pm[ev]), ("market_plus_model", P_both[ev])):
        for oname in ("best", "avg", "pin"):
            O = e[cols(oname)].to_numpy()
            for edge in (0.0, 0.05, 0.10):
                mask = np.isfinite(O) & (P * O > 1 + edge)
                bets[f"{fname}|{oname}|{edge}"] = {"forecast": fname, "odds": oname, "edge": edge,
                                                   **ef.flat_return(O, Ye, mask)}
    # cumulative profit from betting the model's "value" picks (5% edge), for the chart
    curve = pd.DataFrame({"date": e["date"]})
    for oname in ("best", "avg", "pin"):
        O = e[cols(oname)].to_numpy()
        mask = np.isfinite(O) & (Pm[ev] * O > 1.05)
        curve[oname] = np.cumsum(np.where(mask, O * Ye - 1, 0).sum(1))
        curve[f"bets_{oname}"] = np.cumsum(mask.sum(1))
    leak_ok = bool((w.loc[has, "model_fit_end"] < m.loc[has, "date"]).all())
    return {"matches": int(ev.sum()), "eval_from": eval_from, "scores": scores,
            "gain_from_model": gain, "market_minus_model_raw": gain_raw,
            "bets": pd.DataFrame(bets.values()), "curve": curve, "no_lookahead": leak_ok}


def no_crowds(m: pd.DataFrame, Y: np.ndarray) -> dict | None:
    s = ((m["date"] >= NO_CROWDS[0]) & (m["date"] <= NO_CROWDS[1])).to_numpy()
    if s.sum() < 50:
        return None
    pre = (m["date"] < NO_CROWDS[0]) & (m["date"] >= NO_CROWDS[0] - pd.DateOffset(years=5))
    pre = pre.to_numpy()
    res = {}
    for name, mask in (("five_seasons_before", pre), ("no_crowds", s)):
        P = m.loc[mask, cols("cons")].to_numpy()
        Yh = Y[mask, 0]
        diff = ef.mean_ci(Yh - P[:, 0])
        gd = (m.loc[mask, "hg"] - m.loc[mask, "ag"]).to_numpy()
        res[name] = {"matches": int(mask.sum()), "home_win_rate": float(Yh.mean()),
                     "priced_home_win": float(P[:, 0].mean()), "actual_minus_priced": diff,
                     "home_goal_diff": float(gd.mean())}
    return res


# ---------------- charts ----------------

def chart_calibration(table: pd.DataFrame, path: Path):
    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    ax.plot([0, 0.9], [0, 0.9], color=MUTED, lw=1, ls="--", label="perfect calibration")
    ax.errorbar(table["priced"], table["happened"], yerr=[table["happened"] - table["lo"], table["hi"] - table["happened"]],
                fmt="o", color=BLUE, ms=6, lw=1.5, capsize=0, label="betting market (95% interval)")
    _style(ax, "Odds are close to calibrated", "probability implied by the odds", "share that actually happened")
    ax.legend(frameon=False, loc="upper left")
    _save(fig, path)


def chart_longshot(flb: dict, path: Path):
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    for key, color, label, dx in (("average", BLUE, "average odds", -0.13), ("best", ORANGE, "best odds", 0.0),
                                  ("pinnacle", AQUA, "Pinnacle", 0.13)):
        t = flb[key]
        x = np.arange(len(t)) + dx
        ax.errorbar(x, 100 * t["return"], yerr=[100 * (t["return"] - t["lo"]), 100 * (t["hi"] - t["return"])],
                    fmt="o", color=color, ms=6, lw=1.5, capsize=0, label=label)
    ax.axhline(0, color=INK, lw=1)
    t = flb["average"]
    ax.set_xticks(np.arange(len(t)), t["odds"])
    _style(ax, "Long shots lose bettors the most", "decimal odds band (favourites on the left)",
           "profit per 100 staked")
    ax.legend(frameon=False, loc="lower left")
    _save(fig, path)


def chart_margins(mg: pd.DataFrame, path: Path):
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    x = np.arange(len(mg))
    ax.plot(x, 100 * mg["avg_margin"], color=BLUE, lw=2, marker="o", ms=5, label="average bookmaker")
    p = mg["pin_margin"].notna()
    ax.plot(x[p], 100 * mg.loc[p, "pin_margin"], color=AQUA, lw=2, marker="o", ms=5, label="Pinnacle")
    ax.set_xticks(x[::2], [s[2:4] + "/" + s[-2:] for s in mg["season"]][::2])
    ax.set_ylim(0, None)
    _style(ax, "The bookmaker's margin has shrunk", "season", "margin (%)")
    ax.legend(frameon=False)
    _save(fig, path)


def chart_curve(curve: pd.DataFrame, path: Path):
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    for key, color, label in (("best", ORANGE, "best odds across bookmakers"), ("pin", AQUA, "Pinnacle odds"),
                              ("avg", BLUE, "average odds")):
        ax.plot(curve["date"], curve[key], color=color, lw=2, label=label)
    ax.axhline(0, color=INK, lw=1)
    _style(ax, "Betting the model's 'value' picks", "", "cumulative profit (1 unit per bet)")
    ax.legend(frameon=False, loc="lower left")
    _save(fig, path)


def chart_moves(mv: pd.DataFrame, path: Path):
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    for direction, color, dx in (("shortened", ORANGE, -0.08), ("drifted", BLUE, 0.08)):
        t = mv[mv["direction"] == direction]
        x = np.arange(len(t)) + dx
        ax.errorbar(x, 100 * t["return"], yerr=[100 * (t["return"] - t["lo"]), 100 * (t["hi"] - t["return"])],
                    fmt="o", color=color, ms=6, lw=1.5, capsize=0,
                    label="probability rose before kick-off" if direction == "shortened" else "probability fell")
    ax.axhline(0, color=INK, lw=1)
    t = mv[mv["direction"] == "shortened"]
    ax.set_xticks(np.arange(len(t)), [f"≥{100 * v:.0f} pts" for v in t["threshold"]])
    _style(ax, "Late price moves point the right way", "size of move, opening to closing odds",
           "profit per 100 staked at opening odds")
    ax.legend(frameon=False, loc="lower left")
    _save(fig, path)


# ---------------- main ----------------

def _clean(o):
    if isinstance(o, pd.DataFrame):
        return _clean(o.to_dict(orient="records"))
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else round(float(o), 5)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, pd.Timestamp):
        return str(o.date())
    return o


def run(raw_dir: Path, out_dir: Path, tune_cutoff: str = "2008-07-01", eval_from: str = "2010-07-01") -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    m = data.load(raw_dir)
    Y = data.outcome_matrix(m)
    print(f"{len(m):,} matches, {m['season'].nunique()} seasons, leagues {sorted(m['league'].unique())}")

    R = {"matches": len(m), "seasons": [m["season"].min(), m["season"].max()],
         "leagues": sorted(m["league"].unique()), "first_date": m["date"].min(), "last_date": m["date"].max()}
    print("margins..."); R["margins"] = margins_by_season(m)
    print("calibration..."); R["calibration"] = calibration(m, Y)
    print("margin-removal methods..."); R["margin_methods"] = margin_methods(m, Y)
    print("favourite-long-shot..."); R["longshot"] = favourite_longshot(m, Y)
    R["by_outcome"] = by_outcome_returns(m, Y)
    print("opening vs closing..."); R["closing"] = opening_vs_closing(m, Y)
    print("tuning the model on early seasons...")
    hl, tune = tune_half_life(m, tune_cutoff)
    R["model_tuning"] = {"cutoff": tune_cutoff, "half_life_days": hl, "scores": tune}
    print(f"model vs market (half-life {hl} days)..."); R["model"] = model_vs_market(m, Y, hl, eval_from)
    R["no_crowds"] = no_crowds(m, Y)

    chart_calibration(R["calibration"]["table"], out_dir / "calibration.png")
    chart_longshot(R["longshot"], out_dir / "longshot.png")
    chart_margins(R["margins"], out_dir / "margins.png")
    chart_curve(R["model"]["curve"], out_dir / "value_bets.png")
    if R["closing"]:
        chart_moves(R["closing"]["moves"], out_dir / "line_moves.png")
    curve = R["model"].pop("curve")
    curve.to_csv(out_dir / "value_bet_curve.csv", index=False)
    (out_dir / "results.json").write_text(json.dumps(_clean(R), indent=1))
    (out_dir / "report.md").write_text(write_report(_clean(R)))
    print(f"done: {out_dir}")
    return R


def pct(x, d=1):
    return "n/a" if x is None else f"{100 * x:+.{d}f}%"


def write_report(R: dict) -> str:
    c, mm, cl = R["calibration"], R["model"], R["closing"]
    L = [f"# Betting-market efficiency report", "",
         f"{R['matches']:,} matches, {R['seasons'][0]} to {R['seasons'][1]}, leagues {', '.join(R['leagues'])}.", "",
         "## Calibration", "",
         f"Calibration slope {c['pooled']['slope']:.3f} (95% CI {c['pooled']['slope_lo']:.3f}–{c['pooled']['slope_hi']:.3f}); 1 = perfectly calibrated.", "",
         "| Priced | Happened | 95% CI | Outcomes |", "|---|---|---|---|"]
    L += [f"| {r['priced']:.3f} | {r['happened']:.3f} | {r['lo']:.3f}–{r['hi']:.3f} | {r['n']:,} |" for r in c["table"]]
    L += ["", "## Return by odds band (profit per 1 staked)", "", "| Odds | Average odds | Best odds | Pinnacle |", "|---|---|---|---|"]
    pin = {r["odds"]: r for r in R["longshot"]["pinnacle"]}
    best = {r["odds"]: r for r in R["longshot"]["best"]}
    for r in R["longshot"]["average"]:
        b, p = best.get(r["odds"]), pin.get(r["odds"])
        L.append(f"| {r['odds']} | {pct(r['return'])} | {pct(b['return']) if b else '–'} | {pct(p['return']) if p else '–'} |")
    L += ["", "## Margin-removal methods (average odds)", "", "| Method | Log loss | Calibration slope |", "|---|---|---|"]
    L += [f"| {r['method']} | {r['log_loss']:.5f} | {r['slope']:.3f} |" for r in R["margin_methods"]]
    if cl:
        L += ["", "## Opening vs closing odds (Pinnacle)", "",
              f"{cl['matches']:,} matches. Log loss open {cl['log_loss_open']:.4f}, close {cl['log_loss_close']:.4f} "
              f"(difference {cl['diff'][0]:+.4f}, CI {cl['diff'][1]:+.4f} to {cl['diff'][2]:+.4f}).", "",
              "| Move | Direction | Return at opening odds | 95% CI | Bets |", "|---|---|---|---|---|"]
        L += [f"| ≥{100 * r['threshold']:.0f} pts | {r['direction']} | {pct(r['return'])} | {pct(r['lo'])} to {pct(r['hi'])} | {r['bets']:,} |"
              for r in cl["moves"]]
    L += ["", "## Model vs market", "", f"Evaluated on {mm['matches']:,} matches from {mm['eval_from']}; "
          f"model half-life {R['model_tuning']['half_life_days']} days (chosen on seasons before {R['model_tuning']['cutoff']}).", "",
          "| Forecast | Log loss | RPS | Brier |", "|---|---|---|---|"]
    L += [f"| {k} | {v['log_loss']:.4f} | {v['rps']:.4f} | {v['brier']:.4f} |" for k, v in mm["scores"].items()]
    g = mm["gain_from_model"]
    L += ["", f"Adding the model to the market changes log loss by {-g[0]:+.5f} (CI {-g[2]:+.5f} to {-g[1]:+.5f}); negative would mean it helps.",
          f"No look-ahead check passed: {mm['no_lookahead']}.", "",
          "| Forecast | Odds | Edge | Return | 95% CI | Bets |", "|---|---|---|---|---|---|"]
    L += [f"| {r['forecast']} | {r['odds']} | {r['edge']:.0%} | {pct(r['return'])} | {pct(r['lo'])} to {pct(r['hi'])} | {r['bets']:,} |"
          for r in mm["bets"]]
    if R.get("no_crowds"):
        L += ["", "## Matches without crowds (June 2020 – May 2021)", "", "| Period | Matches | Home wins | Priced | Gap (CI) | Home goal diff |", "|---|---|---|---|---|---|"]
        for k, v in R["no_crowds"].items():
            d = v["actual_minus_priced"]
            L.append(f"| {k} | {v['matches']:,} | {v['home_win_rate']:.3f} | {v['priced_home_win']:.3f} | {pct(d[0])} ({pct(d[1])} to {pct(d[2])}) | {v['home_goal_diff']:+.2f} |")
    return "\n".join(L) + "\n"
