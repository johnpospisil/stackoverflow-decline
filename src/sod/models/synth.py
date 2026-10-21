"""P17: synthetic control for monthly Stack Overflow questions (PREREGISTRATION.md section 4).

Outcome: log monthly questions minus each site's own pre-period mean ("demeaned"), 2017-01 to
2026-09. Pre-period 2017-01..2022-11; post-period 2022-12..2026-09. COVID months (2020-03..06)
are left out of every fit and every pre-period statistic.

Weights: non-negative, summing to 1, minimising the pre-period squared gap (all pre months are
the predictors, V = identity). Solved with NNLS plus a heavily weighted sum-to-one row; the main
fit is cross-checked against pysyncon.Synth.

Inference:
  per-month 95% conformal intervals   pysyncon Synth.confidence_interval(method="conformal")
  average-gap 95% intervals           Chernozhukov, Wuthrich & Zhu (2021) test inversion for a
                                      constant effect within a window (all post months; each
                                      year), moving-block permutations, q = 1
  placebo in space                    each donor treated, other 14 donors; rank of post/pre RMSPE
  placebo in time                     fake breaks 2019-11, 2020-11, 2021-11 (pre-period data only)
Also: pre-fit rule (SO pre-RMSPE vs 2x median donor placebo pre-RMSPE), sensitivity (no math,
tech sites added, leave one donor out), SO vs ru.stackoverflow difference-in-differences, and the
platform-wide test (deviation 2026-10-20: monthly ITS per site, median donor gap vs 0.8 x SO's).

Progress: `make progress` (job "synth").

Usage: python -m sod.models.synth
"""

from __future__ import annotations

import json
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.api as sm  # noqa: E402
from scipy.optimize import nnls  # noqa: E402

from sod import config, progress  # noqa: E402

JOB = "synth"
START = pd.Timestamp("2017-01-01")
PRE_END = pd.Timestamp("2022-11-01")
END = pd.Timestamp("2026-09-01")
COVID = (pd.Timestamp("2020-03-01"), pd.Timestamp("2020-06-01"))
FAKE_BREAKS = ("2019-11-01", "2020-11-01", "2021-11-01")
TREATED = config.TREATED
DONORS = list(config.SITE_GROUPS["donor"])
TECH = list(config.SITE_GROUPS["tech_exposed"])
MATH = "math.stackexchange.com"
RU = "ru.stackoverflow.com"
THETA_GRID = np.round(np.arange(-6.0, 1.0001, 0.01), 4)  # log-scale effects to test
ALPHA = 0.05


# --- data ------------------------------------------------------------------------------


def load_logs() -> pd.DataFrame:
    """Wide log monthly questions, months x sites, 2017-01..2026-09."""
    m = pd.read_parquet(config.PANEL_DIR / "site_month.parquet")
    w = m.pivot(index="period", columns="site", values="questions").sort_index()
    w = w.loc[START:END]
    return np.log(w.clip(lower=1).astype(float))


def covid(index: pd.DatetimeIndex) -> np.ndarray:
    return np.asarray((index >= COVID[0]) & (index <= COVID[1]))


def masks(index: pd.DatetimeIndex, pre_end=PRE_END, post_end=END):
    pre = np.asarray(index <= pre_end) & ~covid(index)
    post = np.asarray((index > pre_end) & (index <= post_end)) & ~covid(index)
    return pre, post


def demean(L: pd.DataFrame, pre: np.ndarray) -> pd.DataFrame:
    return L - L[pre].mean()


# --- core fit --------------------------------------------------------------------------


def simplex_weights(y: np.ndarray, X: np.ndarray, penalty: float = 1e4) -> np.ndarray:
    """argmin ||y - Xw||^2  s.t. w >= 0, sum(w) = 1 (NNLS with a weighted sum-to-one row)."""
    A = np.vstack([X, penalty * np.ones(X.shape[1])])
    b = np.append(y, penalty)
    w, _ = nnls(A, b, maxiter=50 * X.shape[1])
    return w / w.sum()


def synth(D: pd.DataFrame, treated: str, donors: list[str], pre: np.ndarray, post: np.ndarray):
    y, X = D[treated].to_numpy(), D[donors].to_numpy()
    w = simplex_weights(y[pre], X[pre])
    gap = y - X @ w
    pre_rmspe = float(np.sqrt(np.mean(gap[pre] ** 2)))
    post_rmspe = float(np.sqrt(np.mean(gap[post] ** 2)))
    return {
        "weights": dict(zip(donors, w, strict=True)),
        "gap": pd.Series(gap, index=D.index),
        "pre_rmspe": pre_rmspe,
        "post_rmspe": post_rmspe,
        "ratio": post_rmspe / pre_rmspe,
        "att_log": float(gap[post].mean()),
    }


def pct(x):
    return 100 * (np.exp(x) - 1)


# --- conformal inference for an average (constant) effect -----------------------------


def cwz_pvalue(D, treated, donors, pre, window, theta) -> float:
    """Chernozhukov-Wuthrich-Zhu p-value for H0: effect = theta in every `window` month."""
    keep = pre | window
    y = D[treated].to_numpy()[keep].copy()
    X = D[donors].to_numpy()[keep]
    win = window[keep]
    y[win] -= theta
    w = simplex_weights(y, X)
    u = np.abs(y - X @ w)
    T, k = len(u), int(win.sum())
    # Window months sit at the end of the series (post-period); moving-block permutations
    # are cyclic shifts, and the statistic is the mean |residual| over the last k positions.
    order = np.r_[np.flatnonzero(~win), np.flatnonzero(win)]
    u = u[order]
    stats = np.array([np.roll(u, -j)[-k:].mean() for j in range(T)])
    return float(np.mean(stats >= stats[0]))


def cwz_interval(D, treated, donors, pre, window, grid=THETA_GRID) -> dict:
    p = np.array([cwz_pvalue(D, treated, donors, pre, window, t) for t in grid])
    accepted = grid[p > ALPHA]
    if accepted.size == 0:
        return {"log_ci": [None, None], "pct_ci": [None, None], "contiguous": True}
    contiguous = accepted.size == (np.ptp(np.flatnonzero(p > ALPHA)) + 1)
    lo, hi = float(accepted.min()), float(accepted.max())
    return {
        "log_ci": [lo, hi],
        "pct_ci": [float(pct(lo)), float(pct(hi))],
        "contiguous": bool(contiguous),
        "at_grid_edge": bool(lo <= grid[0] or hi >= grid[-1]),
        "p_at_zero": float(p[np.argmin(np.abs(grid))]),
    }


def windows(index: pd.DatetimeIndex, post: np.ndarray):
    yield "all_post", post
    for year in sorted(set(index[post].year)):
        yield str(year), post & np.asarray(index.year == year)
    yield "to_2025_09", post & np.asarray(index < pd.Timestamp("2025-10-01"))


# --- pysyncon per-month conformal intervals ----------------------------------------------


def pysyncon_fit_and_ci(D, pre, post, rep=None):
    from pysyncon import Synth

    Z0, Z1 = D[DONORS], D[TREATED]
    pre_idx, post_idx = list(D.index[pre]), list(D.index[post])
    X0, X1 = Z0.loc[pre_idx], Z1.loc[pre_idx]
    # pysyncon rescales each predictor (month) by its sd across units; V = sd^2 undoes that,
    # so the loss is the plain pre-period squared gap, as in simplex_weights().
    V = pd.concat([X0, X1], axis=1).std(axis=1).to_numpy() ** 2
    s = Synth()
    s.fit(X0=X0, X1=X1, Z0=Z0, Z1=Z1, custom_V=V)
    weights = dict(zip(DONORS, (float(x) for x in s.W), strict=True))
    rows = []
    for i, t in enumerate(post_idx, start=1):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ci = s.confidence_interval(
                alpha=ALPHA,
                time_periods=[t],
                tol=0.01,
                pre_periods=pre_idx,
                X0=X0,
                X1=X1,
                Z0=Z0,
                Z1=Z1,
                custom_V=V,
                verbose=False,
            )
        rows.append(ci.reset_index().rename(columns={"time": "period", "index": "period"}))
        if rep:
            rep.update(i, i)
    return weights, pd.concat(rows, ignore_index=True)


# --- supporting analyses ---------------------------------------------------------------


def placebo_space(D, pre, post) -> pd.DataFrame:
    rows = []
    for unit in [TREATED, *DONORS]:
        pool = [d for d in DONORS if d != unit]
        r = synth(D, unit, pool, pre, post)
        rows.append(
            {
                "site": unit,
                **{k: r[k] for k in ("pre_rmspe", "post_rmspe", "ratio", "att_log")},
                "gap": r["gap"],
            }
        )
    df = pd.DataFrame(rows)
    df["rank"] = df["ratio"].rank(ascending=False, method="min").astype(int)
    return df


def placebo_time(L) -> pd.DataFrame:
    rows = []
    for b in FAKE_BREAKS:
        pre, post = masks(L.index, pre_end=pd.Timestamp(b), post_end=PRE_END)
        r = synth(demean(L, pre), TREATED, DONORS, pre, post)
        rows.append(
            {
                "fake_break": b,
                "att_log": r["att_log"],
                "att_pct": pct(r["att_log"]),
                "pre_rmspe": r["pre_rmspe"],
                "ratio": r["ratio"],
            }
        )
    return pd.DataFrame(rows)


def sensitivity(L, D, pre, post) -> pd.DataFrame:
    pools = {
        "preregistered (15 donors)": DONORS,
        "without math": [d for d in DONORS if d != MATH],
        "tech sites added (21 donors)": DONORS + TECH,
    }
    pools.update({f"leave out {d.split('.')[0]}": [x for x in DONORS if x != d] for d in DONORS})
    rows = []
    for name, pool in pools.items():
        r = synth(D, TREATED, pool, pre, post)
        rows.append(
            {
                "variant": name,
                "att_log": r["att_log"],
                "att_pct": pct(r["att_log"]),
                "pre_rmspe": r["pre_rmspe"],
                "top_weights": ", ".join(
                    f"{k.split('.')[0]} {v:.2f}"
                    for k, v in sorted(r["weights"].items(), key=lambda kv: -kv[1])
                    if v >= 0.05
                ),
            }
        )
    return pd.DataFrame(rows)


def did_ru(L) -> dict:
    """Two-way fixed effects with two units = regression of the log difference on post."""
    d = (L[TREATED] - L[RU]).to_frame("diff")
    d = d[~covid(d.index)]
    d["post"] = (d.index > PRE_END).astype(float)
    X = sm.add_constant(d[["post"]])
    fit = sm.OLS(d["diff"], X).fit(cov_type="HAC", cov_kwds={"maxlags": 12})
    b, se = fit.params["post"], fit.bse["post"]
    pre = d[d["post"] == 0]
    t = (pre.index - START).days / 365.25
    trend = sm.OLS(pre["diff"], sm.add_constant(np.asarray(t))).fit(
        cov_type="HAC", cov_kwds={"maxlags": 12}
    )
    by_year = (
        d[d["post"] == 1].groupby(d[d["post"] == 1].index.year)["diff"].mean() - pre["diff"].mean()
    )
    return {
        "did_log": float(b),
        "did_pct": float(pct(b)),
        "did_pct_ci": [float(pct(b - 1.96 * se)), float(pct(b + 1.96 * se))],
        "pre_trend_diff_log_per_year": float(trend.params.iloc[1]),
        "pre_trend_diff_ci": [float(v) for v in trend.conf_int().iloc[1]],
        "by_year_pct": {str(k): float(pct(v)) for k, v in by_year.items()},
    }


def monthly_its_gap(y: pd.Series) -> float:
    """PREREGISTRATION 5.1 adapted to months: trend, Fourier K=4, COVID, level+slope break.
    Returns mean post log gap vs the no-break counterfactual."""
    idx = y.index
    t = (idx - START).days.to_numpy() / 365.25
    X = pd.DataFrame({"const": 1.0, "trend": t}, index=idx)
    phase = 2 * np.pi * (idx.month.to_numpy() - 0.5) / 12
    for k in range(1, 5):
        X[f"sin{k}"], X[f"cos{k}"] = np.sin(k * phase), np.cos(k * phase)
    X["covid"] = covid(idx).astype(float)
    post = np.asarray(idx > PRE_END)
    X["post"] = post.astype(float)
    X["post_slope"] = post * (idx - PRE_END).days.to_numpy() / 365.25
    X = X.loc[:, X.std() > 1e-12].assign(const=1.0)
    fit = sm.OLS(y.to_numpy(), X).fit()
    cf = (
        X.drop(columns=["post", "post_slope"]).to_numpy()
        @ fit.params.drop(["post", "post_slope"]).to_numpy()
    )
    return float((y.to_numpy() - cf)[post].mean())


def platform_wide(L) -> dict:
    gaps = {s: monthly_its_gap(L[s]) for s in [TREATED, *DONORS]}
    so = gaps[TREATED]
    donor_med = float(np.median([gaps[d] for d in DONORS]))
    so_pct, donor_pct = pct(so), pct(donor_med)
    return {
        "own_trend_gap_log": {k.split(".")[0]: v for k, v in gaps.items()},
        "so_gap_log": so,
        "median_donor_gap_log": donor_med,
        "ratio_donor_to_so": donor_med / so,
        "platform_wide_log_rule": bool(donor_med <= 0.8 * so),
        "so_gap_pct": float(so_pct),
        "median_donor_gap_pct": float(donor_pct),
        "original_rule_pp_difference": float(donor_pct - so_pct),
        "platform_wide_original_rule": bool(abs(donor_pct - so_pct) <= 10),
    }


# --- figures ---------------------------------------------------------------------------


def fig_fit(L, main, ci, path):
    pre, _ = masks(L.index)
    mean_so = L[TREATED][pre].mean()
    actual = np.exp(L[TREATED])
    synth_level = np.exp(L[TREATED] - main["gap"])
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.plot(actual.index, actual, color="#D55E00", lw=2.2, label="Stack Overflow")
    ax.plot(
        synth_level.index,
        synth_level,
        color="#009E73",
        lw=1.8,
        ls="--",
        label="Synthetic Stack Overflow (weighted comparison sites)",
    )
    c = ci.set_index("period")
    lo = np.exp(L[TREATED].loc[c.index] - c["upper_ci"])
    hi = np.exp(L[TREATED].loc[c.index] - c["lower_ci"])
    ax.fill_between(
        c.index,
        lo,
        hi,
        color="#009E73",
        alpha=0.15,
        lw=0,
        label="95% conformal interval (per month)",
    )
    ax.axvline(PRE_END + pd.DateOffset(days=29), color="#333333", lw=1, ls=":")
    ax.axvspan(*COVID, color="#cccccc", alpha=0.4, lw=0)
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_ylabel("Questions per month (log scale)")
    ax.set_title("Stack Overflow vs its synthetic control", loc="left")
    ax.legend(fontsize=8, frameon=False, loc="lower left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e5e5e5")
    del mean_so
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_placebos(ps: pd.DataFrame, path):
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for r in ps.itertuples():
        so = r.site == TREATED
        ax.plot(
            r.gap.index,
            r.gap.to_numpy(),
            color="#D55E00" if so else "#999999",
            lw=2.2 if so else 0.8,
            alpha=1 if so else 0.6,
            zorder=3 if so else 1,
        )
        if not so:
            ax.annotate(
                r.site.split(".")[0],
                (r.gap.index[-1], r.gap.iloc[-1]),
                fontsize=7,
                color="#777777",
                xytext=(3, 0),
                textcoords="offset points",
                va="center",
            )
    ax.axhline(0, color="#333333", lw=0.8)
    ax.axvline(PRE_END + pd.DateOffset(days=29), color="#333333", lw=1, ls=":")
    ax.set_ylabel("Gap: log actual minus log synthetic")
    ax.set_title(
        "Placebo test: each comparison site treated as if it were Stack Overflow (orange)",
        loc="left",
        fontsize=11,
    )
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e5e5e5")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# --- run -------------------------------------------------------------------------------

TASKS = {
    "main_fit": 1,
    "conformal_per_month": 46,
    "conformal_average": 7 * 30,
    "placebo_space": 16,
    "placebo_time": 3,
    "sensitivity": 18,
    "did_platform": 2,
}


def run() -> dict:
    progress.write_manifest(JOB, TASKS)
    L = load_logs()
    pre, post = masks(L.index)
    D = demean(L, pre)

    rep = progress.Reporter(JOB, "main_fit", 1)
    main = synth(D, TREATED, DONORS, pre, post)
    rep.finish(1)

    rep = progress.Reporter(JOB, "conformal_per_month", int(post.sum()))
    pw, ci = pysyncon_fit_and_ci(D, pre, post, rep)
    rep.finish(len(ci))

    rep = progress.Reporter(JOB, "conformal_average", 7)
    avg = {}
    for i, (name, win) in enumerate(windows(L.index, post), start=1):
        gap = main["gap"][win].mean()
        avg[name] = {
            "months": int(win.sum()),
            "att_log": float(gap),
            "att_pct": float(pct(gap)),
            **cwz_interval(D, TREATED, DONORS, pre, win),
        }
        rep._last = 0
        rep.update(i, i)
    rep.finish(len(avg))

    rep = progress.Reporter(JOB, "placebo_space", 1)
    ps = placebo_space(D, pre, post)
    rep.finish(len(ps))
    so_row = ps[ps["site"] == TREATED].iloc[0]
    donor_pre = ps[ps["site"] != TREATED]["pre_rmspe"]

    rep = progress.Reporter(JOB, "placebo_time", 1)
    pt = placebo_time(L)
    rep.finish(len(pt))

    rep = progress.Reporter(JOB, "sensitivity", 1)
    sens = sensitivity(L, D, pre, post)
    rep.finish(len(sens))

    rep = progress.Reporter(JOB, "did_platform", 1)
    did = did_ru(L)
    plat = platform_wide(L)
    rep.finish(2)

    fit_ok = main["pre_rmspe"] <= 2 * float(donor_pre.median())
    att, ci_all = avg["all_post"]["att_pct"], avg["all_post"]["pct_ci"]
    # Two readings of "95% conformal interval for the ATT" (decision pending, see P17 findings):
    #  constant_effect  CWZ test inversion for one effect shared by all post months
    #  monthly_average  mean of pysyncon's per-month conformal bounds
    monthly_ci = [float(pct(ci["lower_ci"].mean())), float(pct(ci["upper_ci"].mean()))]
    readings = {
        "constant_effect": ci_all,
        "monthly_average": monthly_ci,
    }
    common = {
        "att_le_minus10": att <= -10,
        "so_ranks_first": int(so_row["rank"]) == 1,
        "no_time_placebo_as_large": bool((pt["att_log"].abs() < abs(main["att_log"])).all()),
    }
    h1 = {
        name: {**common, "ci_excludes_zero": c[1] is not None and c[1] < 0}
        for name, c in readings.items()
    }
    summary = {
        "pre_period": [str(START.date()), str(PRE_END.date())],
        "post_period": [str(L.index[post][0].date()), str(L.index[post][-1].date())],
        "weights": {k: round(v, 4) for k, v in main["weights"].items() if v > 1e-4},
        "weights_pysyncon": {k: v for k, v in pw.items() if v > 1e-4},
        "max_weight_difference_vs_pysyncon": float(
            max(abs(main["weights"][k] - pw.get(k, 0.0)) for k in DONORS)
        ),
        "pre_rmspe": main["pre_rmspe"],
        "median_donor_placebo_pre_rmspe": float(donor_pre.median()),
        "prefit_ok": bool(fit_ok),
        "primary_estimator": "synthetic control" if fit_ok else "interrupted time series",
        "att": avg,
        "placebo_space": {
            "so_rank": int(so_row["rank"]),
            "n": len(ps),
            "p_value": int(so_row["rank"]) / len(ps),
        },
        "placebo_time": pt.round(4).to_dict(orient="records"),
        "att_interval_readings_pct": readings,
        "months_interval_excludes_zero": int((ci["upper_ci"] < 0).sum()),
        "h1_checks": h1,
        "h1_supported_by_reading": {k: bool(fit_ok and all(v.values())) for k, v in h1.items()},
        "did_ru": did,
        "platform_wide": plat,
    }
    out = config.REPO_ROOT / "report"
    ci.to_csv(out / "tables" / "synth_conformal_per_month.csv", index=False)
    ps.drop(columns="gap").round(4).to_csv(out / "tables" / "synth_placebo_space.csv", index=False)
    sens.round(4).to_csv(out / "tables" / "synth_sensitivity.csv", index=False)
    (out / "qa" / "synth_summary.json").write_text(json.dumps(summary, indent=2, default=float))
    fig_fit(L, main, ci, config.FIGURE_DIR / "synth_fit.png")
    fig_placebos(ps, config.FIGURE_DIR / "synth_placebo_space.png")
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=float))
