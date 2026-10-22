"""P15: interrupted time series on weekly Stack Overflow questions (PREREGISTRATION.md 5.1).

log(questions_w) = a + b*trend + Fourier(K=4, yearly) + holiday weeks (Christmas, New Year,
US Thanksgiving) + COVID indicator (weeks overlapping 2020-03-11..2020-06-30)
+ level*post + slope*post*(years since the break) + e,   post = week >= 2022-11-28.
Newey-West (HAC) standard errors with 8 lags.

The counterfactual is the fitted model with level = slope = 0. Gaps (actual vs counterfactual):
  mean log gap = mean over the window's weeks of log(actual) - log(counterfactual) -> exp() - 1
    (over all post weeks this equals level + slope * mean(years since break); per year it shows
    the observed path, which a straight-line slope break smooths over)
  cumulative gap = sum(actual) / sum(counterfactual) - 1   (counterfactual with Duan smearing)
Intervals for both come from 4,000 draws of the coefficients (normal, HAC covariance).

Fits: "preregistered" (sample from 2017-01-02) and "post_covid" (exploratory, from 2020-07-06;
deviation 2026-10-21). Diagnostics: Ljung-Box, Durbin-Watson, residual ACF, and a pre-period
holdout (fit to 2021-11, forecast 2021-11-29..2022-11-27 without break terms).

Usage: python -m sod.models.its
"""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.api as sm  # noqa: E402
from statsmodels.graphics.tsaplots import plot_acf  # noqa: E402
from statsmodels.stats.diagnostic import acorr_ljungbox  # noqa: E402
from statsmodels.stats.stattools import durbin_watson  # noqa: E402

from sod import config  # noqa: E402

BREAK = pd.Timestamp(config.BREAK_WEEK)
STARTS = {"preregistered": "2017-01-02", "post_covid": "2020-07-06"}
COVID = (pd.Timestamp("2020-03-11"), pd.Timestamp("2020-06-30"))
K = 4
HAC_LAGS = 8
N_DRAWS = 4000
BREAK_TERMS = ["post", "post_slope"]


def load_weekly(site: str = config.TREATED) -> pd.Series:
    w = pd.read_parquet(config.PANEL_DIR / "site_week.parquet")
    w = w[(w["site"] == site) & ~w["partial_period"]]
    return w.set_index("period")["questions"].astype(float).sort_index()


def thanksgiving(year: int) -> pd.Timestamp:
    nov1 = pd.Timestamp(f"{year}-11-01")
    return nov1 + pd.Timedelta(days=(3 - nov1.dayofweek) % 7 + 21)  # 4th Thursday


def _week_start(ts: pd.Timestamp) -> pd.Timestamp:
    return (ts - pd.Timedelta(days=ts.dayofweek)).normalize()


def design(weeks: pd.DatetimeIndex, start: pd.Timestamp, break_week=BREAK) -> pd.DataFrame:
    """Regressors for Monday-dated weeks. Trend in years since `start`."""
    t = (weeks - start).days.to_numpy() / 365.25
    X = pd.DataFrame(index=weeks)
    X["const"] = 1.0
    X["trend"] = t
    mid = weeks + pd.Timedelta(days=3)  # Thursday: the week's position in the year
    phase = 2 * np.pi * (mid.dayofyear.to_numpy() - 1) / 365.25
    for k in range(1, K + 1):
        X[f"sin{k}"] = np.sin(k * phase)
        X[f"cos{k}"] = np.cos(k * phase)
    years = range(weeks.min().year - 1, weeks.max().year + 2)
    xmas = {_week_start(pd.Timestamp(f"{y}-12-25")) for y in years}
    newyear = {_week_start(pd.Timestamp(f"{y}-01-01")) for y in years}
    tg = {_week_start(thanksgiving(y)) for y in years}
    X["christmas"] = weeks.isin(xmas).astype(float)
    X["new_year"] = (weeks.isin(newyear) & ~weeks.isin(xmas)).astype(float)
    X["thanksgiving"] = weeks.isin(tg).astype(float)
    week_end = weeks + pd.Timedelta(days=6)
    X["covid"] = ((week_end >= COVID[0]) & (weeks <= COVID[1])).astype(float)
    post = (weeks >= break_week).astype(float)
    X["post"] = post
    X["post_slope"] = post * (weeks - break_week).days.to_numpy() / 365.25
    return X


def fit(y: pd.Series, start: str, end: pd.Timestamp | None = None, break_week=BREAK):
    s = pd.Timestamp(start)
    y = y.loc[s:end] if end is not None else y.loc[s:]
    X = design(y.index, s, break_week)
    if X["post"].sum() == 0:
        X = X.drop(columns=BREAK_TERMS)
    X = X.loc[:, X.std() > 0].assign(const=1.0)  # drop dummies that never fire in the sample
    model = sm.OLS(np.log(y), X).fit(cov_type="HAC", cov_kwds={"maxlags": HAC_LAGS})
    return model, X, y


def _pct(x):
    return 100 * (np.exp(x) - 1)


def gaps(model, X: pd.DataFrame, y: pd.Series, seed: int = 0) -> dict:
    """Level/slope changes and post-period gaps with 95% intervals."""
    rng = np.random.default_rng(seed)
    params, cov = model.params, model.cov_params()
    draws = pd.DataFrame(
        rng.multivariate_normal(params.to_numpy(), cov.to_numpy(), N_DRAWS), columns=params.index
    )
    post = X["post"] == 1
    Xp = X[post]
    pre_resid = model.resid[~post]
    smear = float(np.exp(pre_resid).mean())  # Duan smearing for the counterfactual level
    Xcf = Xp.drop(columns=BREAK_TERMS)

    def ci(v):
        return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]

    out = {}
    for name in BREAK_TERMS:
        out[name] = {
            "log": float(params[name]),
            "pct": float(_pct(params[name])),
            "pct_ci": [
                float(_pct(params[name] - 1.96 * model.bse[name])),
                float(_pct(params[name] + 1.96 * model.bse[name])),
            ],
        }
    out["post_slope"]["unit"] = "change in % growth per year"

    def windows():
        yield "all_post", np.ones(post.sum(), bool)
        yr = Xp.index.year
        for year in sorted(set(yr)):
            yield str(year), (yr == year)
        yield "to_2025_09", Xp.index < pd.Timestamp("2025-10-01")

    actual = y[post].to_numpy()
    cf_draws = np.exp(draws[Xcf.columns].to_numpy() @ Xcf.to_numpy().T) * smear  # draws x weeks
    cf_point = np.exp(Xcf.to_numpy() @ params[Xcf.columns].to_numpy()) * smear
    log_actual = np.log(actual)
    gap_draws = log_actual - draws[Xcf.columns].to_numpy() @ Xcf.to_numpy().T
    gap_point = log_actual - Xcf.to_numpy() @ params[Xcf.columns].to_numpy()
    out["windows"] = {}
    for name, mask in windows():
        mlog = gap_point[mask].mean()
        cum = actual[mask].sum() / cf_point[mask].sum() - 1
        cum_d = actual[mask].sum() / cf_draws[:, mask].sum(axis=1) - 1
        out["windows"][name] = {
            "weeks": int(mask.sum()),
            "mean_log_gap": float(mlog),
            "mean_gap_pct": float(_pct(mlog)),
            "mean_gap_pct_ci": [float(_pct(v)) for v in ci(gap_draws[:, mask].mean(axis=1))],
            "actual_questions": float(actual[mask].sum()),
            "counterfactual_questions": float(cf_point[mask].sum()),
            "cumulative_gap_pct": float(100 * cum),
            "cumulative_gap_pct_ci": [100 * v for v in ci(cum_d)],
        }
    return out


def diagnostics(model, X: pd.DataFrame) -> dict:
    r = model.resid
    pre = r[X["post"] == 0]
    post = r[X["post"] == 1]
    lb = acorr_ljungbox(r, lags=[8, 52])
    lb_pre = acorr_ljungbox(pre, lags=[8, 52])
    return {
        "n_weeks": int(len(r)),
        "n_pre": int(len(pre)),
        "n_post": int(len(post)),
        "r2": float(model.rsquared),
        "resid_sd_pre": float(pre.std()),
        "resid_sd_post": float(post.std()),
        "durbin_watson": float(durbin_watson(r)),
        "acf_lag1_pre": float(pre.autocorr(1)),
        "acf_lag1_post": float(post.autocorr(1)),
        "ljung_box_p_lag8": float(lb["lb_pvalue"].iloc[0]),
        "ljung_box_p_lag52": float(lb["lb_pvalue"].iloc[1]),
        "ljung_box_pre_p_lag8": float(lb_pre["lb_pvalue"].iloc[0]),
    }


def holdout(y: pd.Series, start: str) -> dict:
    """Fit to 2021-11-28 (no break), forecast the next 52 pre-period weeks."""
    end = pd.Timestamp("2021-11-22")
    model, X, _ = fit(y, start, end=end)
    h = y.loc[end + pd.Timedelta(days=7) : BREAK - pd.Timedelta(days=7)]
    Xh = design(h.index, pd.Timestamp(start))[X.columns]
    pred = Xh.to_numpy() @ model.params.to_numpy()
    err = np.log(h.to_numpy()) - pred
    return {
        "weeks": int(len(h)),
        "mean_error_pct": float(_pct(err.mean())),
        "rmse_log": float(np.sqrt((err**2).mean())),
        "note": "positive = actual above the trend forecast",
    }


# --- figures ---------------------------------------------------------------------------


def _counterfactual_series(model, X):
    cf = X.drop(columns=BREAK_TERMS) @ model.params.drop(BREAK_TERMS)
    return np.exp(model.fittedvalues), np.exp(cf)


def fig_fit(results: dict, y: pd.Series, path) -> None:
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.plot(y.index, y.to_numpy(), color="#bbbbbb", lw=0.8, label="Actual (weekly)")
    styles = {
        "preregistered": ("#D55E00", "-", "pre-registered, trend from 2017"),
        "post_covid": ("#0072B2", "--", "exploratory, trend from 2020-07"),
    }
    for name, (model, X, yy) in results.items():
        c, ls, lab = styles[name]
        fitted, cf = _counterfactual_series(model, X)
        post = X["post"] == 1
        ax.plot(yy.index, fitted, color=c, lw=1.4, ls=ls, label=f"Fitted, {lab}")
        ax.plot(
            yy.index[post],
            cf[post],
            color=c,
            lw=1.4,
            ls=ls,
            alpha=0.55,
            label=f"No-break counterfactual, {lab}",
        )
    ax.axvline(BREAK, color="#333333", lw=1, ls=":")
    ax.text(
        BREAK,
        0.97,
        " ChatGPT week\n (2022-11-28)",
        fontsize=8,
        va="top",
        transform=ax.get_xaxis_transform(),
    )
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_ylabel("Questions per week (log scale)")
    ax.set_title("Stack Overflow weekly questions: interrupted time series", loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e5e5e5")
    ax.legend(fontsize=8, frameon=False, loc="lower left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_diagnostics(model, X, path) -> None:
    r = model.resid
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(13, 3.8))
    a1.plot(r.index, r.to_numpy(), color="#333333", lw=0.7)
    a1.axhline(0, color="#999999", lw=0.8)
    a1.axvline(BREAK, color="#D55E00", lw=1, ls=":")
    a1.set_title("Residuals (log), pre-registered fit", loc="left", fontsize=10)
    plot_acf(r[X["post"] == 0], lags=60, ax=a2, title="")
    a2.set_title("Residual autocorrelation, pre-period", loc="left", fontsize=10)
    plot_acf(r[X["post"] == 1], lags=60, ax=a3, title="")
    a3.set_title("Residual autocorrelation, post-period", loc="left", fontsize=10)
    for a in (a1, a2, a3):
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# --- run -------------------------------------------------------------------------------


def run() -> dict:
    y = load_weekly()
    results = {name: fit(y, start) for name, start in STARTS.items()}
    summary = {"last_week": str(y.index.max().date()), "fits": {}}
    rows = []
    for name, (model, X, yy) in results.items():
        g = gaps(model, X, yy)
        summary["fits"][name] = {
            "sample_start": STARTS[name],
            **g,
            "diagnostics": diagnostics(model, X),
            "holdout_2021_12_to_2022_11": holdout(y, STARTS[name]),
            "coefficients": {
                k: [float(model.params[k]), float(model.bse[k])] for k in model.params.index
            },
        }
        for term in BREAK_TERMS:
            rows.append(
                {
                    "fit": name,
                    "estimate": term,
                    "pct": g[term]["pct"],
                    "low": g[term]["pct_ci"][0],
                    "high": g[term]["pct_ci"][1],
                }
            )
        for wname, w in g["windows"].items():
            rows.append(
                {
                    "fit": name,
                    "estimate": f"mean_gap_{wname}",
                    "pct": w["mean_gap_pct"],
                    "low": w["mean_gap_pct_ci"][0],
                    "high": w["mean_gap_pct_ci"][1],
                }
            )
            rows.append(
                {
                    "fit": name,
                    "estimate": f"cumulative_gap_{wname}",
                    "pct": w["cumulative_gap_pct"],
                    "low": w["cumulative_gap_pct_ci"][0],
                    "high": w["cumulative_gap_pct_ci"][1],
                }
            )
    fig_fit(results, y.loc["2016-01-01":], config.FIGURE_DIR / "its_fit.png")
    fig_diagnostics(*results["preregistered"][:2], config.FIGURE_DIR / "its_diagnostics.png")
    tables = config.REPORT_DIR / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).round(2).to_csv(tables / "its_estimates.csv", index=False)
    qa = config.REPORT_DIR / "qa"
    (qa / "its_summary.json").write_text(json.dumps(summary, indent=2))
    config.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for name, (model, _, _) in results.items():
        model.save(config.MODEL_DIR / f"its_{name}.pickle")
    return summary


if __name__ == "__main__":
    s = run()
    est = pd.read_csv(config.REPORT_DIR / "tables" / "its_estimates.csv")
    print(est.to_string(index=False))
    for name, f in s["fits"].items():
        print(name, json.dumps(f["diagnostics"]), json.dumps(f["holdout_2021_12_to_2022_11"]))
