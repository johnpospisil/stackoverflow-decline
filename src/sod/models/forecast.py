"""P16: forecast counterfactual for monthly Stack Overflow questions (PREREGISTRATION.md 5.2).

Two forecasters trained on log monthly questions over the pre-period (2017-01 to 2022-11) and
projected to 2026-09 with 95% prediction intervals:
  ETS      statsmodels ETSModel, additive error and seasonality (period 12); trend chosen by
           AICc among none / additive / additive damped. ETS has no regressors, so the COVID
           months (2020-03..2020-06) are replaced by linear interpolation of the log series
           before fitting ("excluded from fitting", PREREGISTRATION.md section 2).
  Prophet  linear growth, yearly seasonality, COVID months as a holiday window.

Gap = log(actual) - log(forecast path), averaged over a window, as % via exp() - 1. Intervals:
2.5/97.5 percentiles over 2,000 simulated forecast paths (ETS) or posterior predictive samples
(Prophet). Cumulative gap = sum(actual) / sum(path) - 1, same intervals.

Backtest (pre-registered): train 2017-01..2019-11, forecast 2019-12..2022-11; error measured
with and without the COVID months.

Usage: python -m sod.models.forecast
"""

from __future__ import annotations

import json
import logging
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from statsmodels.tsa.exponential_smoothing.ets import ETSModel  # noqa: E402

from sod import config  # noqa: E402

TRAIN_START = pd.Timestamp("2017-01-01")
TRAIN_END = pd.Timestamp("2022-11-01")
BACKTEST_END = pd.Timestamp("2019-11-01")
COVID = (pd.Timestamp("2020-03-01"), pd.Timestamp("2020-06-01"))
N_PATHS = 2000
SEED = 0
TRENDS = {"none": None, "additive": "add", "damped": "add_damped"}


def load_monthly(site: str = config.TREATED) -> pd.Series:
    m = pd.read_parquet(config.PANEL_DIR / "site_month.parquet")
    m = m[(m["site"] == site) & ~m["partial_period"]]
    s = m.set_index("period")["questions"].astype(float).sort_index()
    s.index = pd.DatetimeIndex(s.index, freq="MS")
    return s.loc[TRAIN_START:]


def covid_mask(index: pd.DatetimeIndex) -> np.ndarray:
    return (index >= COVID[0]) & (index <= COVID[1])


# --- ETS -------------------------------------------------------------------------------


def fit_ets(log_y: pd.Series):
    y = log_y.copy()
    y[covid_mask(y.index)] = np.nan
    y = y.interpolate()
    fits = {}
    for name, trend in TRENDS.items():
        damped = trend == "add_damped"
        model = ETSModel(
            y,
            error="add",
            trend="add" if trend else None,
            damped_trend=damped,
            seasonal="add",
            seasonal_periods=12,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fits[name] = model.fit(disp=False, maxiter=2000)
    best = min(fits, key=lambda k: fits[k].aicc)
    return fits[best], best, {k: float(f.aicc) for k, f in fits.items()}


def ets_paths(res, horizon: int) -> np.ndarray:
    """Simulated log paths, shape (horizon, N_PATHS)."""
    sims = res.simulate(horizon, repetitions=N_PATHS, anchor="end", rng=np.random.default_rng(SEED))
    return np.asarray(sims)


# --- Prophet ---------------------------------------------------------------------------


def fit_prophet(log_y: pd.Series):
    from prophet import Prophet

    logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
    logging.getLogger("prophet").setLevel(logging.WARNING)
    covid = pd.DataFrame(
        {
            "holiday": "covid",
            "ds": pd.date_range(*COVID, freq="MS"),
            "lower_window": 0,
            "upper_window": 0,
        }
    )
    m = Prophet(
        growth="linear",
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        holidays=covid,
        interval_width=0.95,
        uncertainty_samples=N_PATHS,
    )
    np.random.seed(SEED)
    m.fit(pd.DataFrame({"ds": log_y.index, "y": log_y.to_numpy()}))
    return m


def prophet_paths(m, index: pd.DatetimeIndex) -> np.ndarray:
    np.random.seed(SEED)
    samples = m.predictive_samples(pd.DataFrame({"ds": index}))
    return np.asarray(samples["yhat"])  # (horizon, N_PATHS)


# --- gaps and backtest -----------------------------------------------------------------


def _pct(x):
    return 100 * (np.exp(x) - 1)


def _ci(v):
    return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]


def windows(index: pd.DatetimeIndex):
    yield "all_post", np.ones(len(index), bool)
    for year in sorted(set(index.year)):
        yield str(year), index.year == year
    yield "to_2025_09", index < pd.Timestamp("2025-10-01")


def gaps(actual: pd.Series, paths: np.ndarray) -> dict:
    """actual: post-period counts; paths: log forecast paths (months x draws)."""
    la = np.log(actual.to_numpy())[:, None]
    gap = la - paths  # months x draws
    level = np.exp(paths)
    out = {}
    for name, mask in windows(actual.index):
        g = gap[mask].mean(axis=0)
        cum = actual.to_numpy()[mask].sum() / level[mask].sum(axis=0) - 1
        out[name] = {
            "months": int(mask.sum()),
            "mean_gap_pct": float(_pct(np.median(g))),
            "mean_gap_pct_ci": [float(_pct(v)) for v in _ci(g)],
            "cumulative_gap_pct": float(100 * np.median(cum)),
            "cumulative_gap_pct_ci": [100 * v for v in _ci(cum)],
            "counterfactual_questions_median": float(np.median(level[mask].sum(axis=0))),
            "actual_questions": float(actual.to_numpy()[mask].sum()),
        }
    return out


def forecast_band(paths: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "median": np.exp(np.median(paths, axis=1)),
            "low": np.exp(np.percentile(paths, 2.5, axis=1)),
            "high": np.exp(np.percentile(paths, 97.5, axis=1)),
        }
    )


def accuracy(actual: pd.Series, paths: np.ndarray) -> dict:
    err = np.log(actual.to_numpy()) - np.median(paths, axis=1)
    lo, hi = np.percentile(paths, 2.5, axis=1), np.percentile(paths, 97.5, axis=1)
    inside = (np.log(actual.to_numpy()) >= lo) & (np.log(actual.to_numpy()) <= hi)
    keep = ~covid_mask(actual.index)

    def summ(mask):
        e = err[mask]
        return {
            "months": int(mask.sum()),
            "mean_error_pct": float(_pct(e.mean())),
            "mape_pct": float(100 * np.mean(np.abs(np.exp(e) - 1))),
            "rmse_log": float(np.sqrt(np.mean(e**2))),
            "coverage_95": float(inside[mask].mean()),
            "last_12_mean_error_pct": float(_pct(e[-12:].mean())),
        }

    horizon_year = np.arange(len(err)) // 12 + 1
    by_year = {
        str(int(k)): float(_pct(err[horizon_year == k].mean())) for k in np.unique(horizon_year)
    }
    return {
        "all": summ(np.ones(len(err), bool)),
        "excl_covid": summ(keep),
        "mean_error_pct_by_horizon_year": by_year,
    }


def run_model(name: str, log_train: pd.Series, horizon_index: pd.DatetimeIndex):
    if name == "ets":
        res, trend, aicc = fit_ets(log_train)
        return ets_paths(res, len(horizon_index)), {"trend": trend, "aicc": aicc}
    m = fit_prophet(log_train)
    return prophet_paths(m, horizon_index), {}


# --- figures ---------------------------------------------------------------------------

COLORS = {"ets": "#0072B2", "prophet": "#009E73"}
LABELS = {"ets": "ETS (exponential smoothing)", "prophet": "Prophet"}


def fig_forecasts(y: pd.Series, bands: dict, path, title: str, start="2017-01-01") -> None:
    fig, ax = plt.subplots(figsize=(11, 5.5))
    yy = y.loc[start:]
    ax.plot(yy.index, yy.to_numpy(), color="#333333", lw=1.6, label="Actual (monthly)")
    for name, (idx, b) in bands.items():
        ax.fill_between(idx, b["low"], b["high"], color=COLORS[name], alpha=0.15, lw=0)
        ax.plot(
            idx,
            b["median"],
            color=COLORS[name],
            lw=1.6,
            ls="--",
            label=f"{LABELS[name]} forecast, 95% interval",
        )
    cut = min(idx[0] for idx, _ in bands.values())
    ax.axvline(cut, color="#999999", lw=1, ls=":")
    ax.set_yscale("log")
    ax.set_ylim(yy.min() / 3, yy.max() * 3)  # keep runaway interval tails from hiding the data
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_ylabel("Questions per month (log scale)")
    ax.set_title(title, loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e5e5e5")
    ax.legend(fontsize=8, frameon=False, loc="lower left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# --- run -------------------------------------------------------------------------------


def run() -> dict:
    y = load_monthly()
    log_y = np.log(y)
    train = log_y.loc[:TRAIN_END]
    post = y.loc[TRAIN_END + pd.DateOffset(months=1) :]
    bt_train = log_y.loc[:BACKTEST_END]
    bt_test = y.loc[BACKTEST_END + pd.DateOffset(months=1) : TRAIN_END]

    summary = {
        "train": [str(TRAIN_START.date()), str(TRAIN_END.date())],
        "post": [str(post.index[0].date()), str(post.index[-1].date())],
        "models": {},
    }
    rows, bands, bt_bands = [], {}, {}
    for name in ("ets", "prophet"):
        paths, info = run_model(name, train, post.index)
        g = gaps(post, paths)
        bt_paths, bt_info = run_model(name, bt_train, bt_test.index)
        summary["models"][name] = {
            **info,
            "gaps": g,
            "backtest": {
                **accuracy(bt_test, bt_paths),
                **({"trend": bt_info["trend"]} if "trend" in bt_info else {}),
            },
        }
        bands[name] = (post.index, forecast_band(paths))
        bt_bands[name] = (bt_test.index, forecast_band(bt_paths))
        for w, v in g.items():
            rows.append(
                {
                    "model": name,
                    "window": w,
                    "estimate": "mean_gap",
                    "pct": v["mean_gap_pct"],
                    "low": v["mean_gap_pct_ci"][0],
                    "high": v["mean_gap_pct_ci"][1],
                }
            )
            rows.append(
                {
                    "model": name,
                    "window": w,
                    "estimate": "cumulative_gap",
                    "pct": v["cumulative_gap_pct"],
                    "low": v["cumulative_gap_pct_ci"][0],
                    "high": v["cumulative_gap_pct_ci"][1],
                }
            )
    fig_forecasts(
        y,
        bands,
        config.FIGURE_DIR / "forecast_counterfactual.png",
        "Stack Overflow monthly questions vs forecasts trained to 2022-11",
    )
    fig_forecasts(
        y.loc[:TRAIN_END],
        bt_bands,
        config.FIGURE_DIR / "forecast_backtest.png",
        "Backtest: trained to 2019-11, forecasting 2019-12 to 2022-11",
    )
    tables = config.REPORT_DIR / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).round(2).to_csv(tables / "forecast_estimates.csv", index=False)
    (config.REPORT_DIR / "qa" / "forecast_summary.json").write_text(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    s = run()
    for name, mdl in s["models"].items():
        print(f"== {name} {mdl.get('trend', '')} {mdl.get('aicc', '')}")
        for w, v in mdl["gaps"].items():
            print(
                f"  {w:<11} mean {v['mean_gap_pct']:7.1f} {np.round(v['mean_gap_pct_ci'], 1)}"
                f"  cum {v['cumulative_gap_pct']:7.1f} {np.round(v['cumulative_gap_pct_ci'], 1)}"
            )
        print("  backtest", json.dumps(mdl["backtest"]))
