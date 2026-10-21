"""P14: descriptive analysis of the site panels. No models of the post-period here.

Used by notebooks/01_eda.ipynb. Pure functions take panel DataFrames so they can be tested;
`run()` loads the panels, writes report/figures/eda_*.png and report/qa/eda_summary.json.

Pre-period = 2017-01 to 2022-11 (the pre-registered synthetic-control window). Months in the
COVID exclusion window (2020-03 to 2020-06) are left out of slope and seasonality fits.

Usage: python -m sod.eda
"""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.api as sm  # noqa: E402

from sod import config  # noqa: E402
from sod.db import connect  # noqa: E402

PRE_START, PRE_END = pd.Timestamp("2017-01-01"), pd.Timestamp("2022-11-01")
COVID = (pd.Timestamp("2020-03-01"), pd.Timestamp("2020-06-01"))  # months, inclusive
BREAK = pd.Timestamp(config.BREAK_DATE)
GROUPS = ("treated", "so_language", "tech_exposed", "donor")
LABELS = {
    "treated": "Stack Overflow",
    "so_language": "Stack Overflow in other languages",
    "tech_exposed": "Other tech sites",
    "donor": "Comparison sites (15)",
    "context": "Meta Stack Overflow",
}
# Okabe-Ito, fixed per group (colour-blind safe).
COLORS = {
    "treated": "#D55E00",
    "so_language": "#E69F00",
    "tech_exposed": "#0072B2",
    "donor": "#009E73",
    "context": "#999999",
}
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def short(site: str) -> str:
    return site.replace(".stackexchange.com", "").replace(".com", "")


def load_month() -> pd.DataFrame:
    m = pd.read_parquet(config.PANEL_DIR / "site_month.parquet")
    m["group"] = m["site"].map(config.site_group)
    return m[~m["partial_period"]]


def load_week() -> pd.DataFrame:
    w = pd.read_parquet(config.PANEL_DIR / "site_week.parquet")
    w["group"] = w["site"].map(config.site_group)
    return w[~w["partial_period"]]


def pre_months(df: pd.DataFrame, drop_covid: bool = True) -> pd.DataFrame:
    keep = (df["period"] >= PRE_START) & (df["period"] <= PRE_END)
    if drop_covid:
        keep &= ~df["period"].between(*COVID)
    return df[keep]


# --- trends --------------------------------------------------------------------------


def indexed(m: pd.DataFrame, col: str = "questions", base_year: int = 2019) -> pd.DataFrame:
    """Each site's monthly series as an index, base-year monthly mean = 100."""
    base = m[m["period"].dt.year == base_year].groupby("site")[col].mean()
    out = m[["site", "group", "period"]].copy()
    out["index"] = 100 * m[col] / m["site"].map(base)
    return out


def group_index(ix: pd.DataFrame) -> pd.DataFrame:
    """Median, min and max of the site indices in each group and month."""
    return (
        ix.groupby(["group", "period"])["index"]
        .agg(median="median", low="min", high="max", n="size")
        .reset_index()
    )


# --- pre-period slopes ---------------------------------------------------------------


def pre_slope(g: pd.DataFrame, col: str = "questions") -> dict:
    """OLS of log monthly counts on a linear trend + calendar-month dummies over the
    pre-period (COVID months dropped). Returns % change per year with a 95% HAC interval."""
    g = pre_months(g).sort_values("period")
    years = (g["period"] - PRE_START).dt.days / 365.25
    X = pd.get_dummies(g["period"].dt.month, prefix="m", drop_first=True, dtype=float)
    X.insert(0, "trend", years.to_numpy())
    X = sm.add_constant(X)
    fit = sm.OLS(np.log(g[col].clip(lower=1)).to_numpy(), X).fit(
        cov_type="HAC", cov_kwds={"maxlags": 6}
    )
    b, se = fit.params["trend"], fit.bse["trend"]
    pct = lambda x: 100 * (np.exp(x) - 1)  # noqa: E731
    return {
        "pct_per_year": pct(b),
        "low": pct(b - 1.96 * se),
        "high": pct(b + 1.96 * se),
        "n_months": len(g),
    }


def pre_slopes(m: pd.DataFrame) -> pd.DataFrame:
    rows = [{"site": s, "group": g["group"].iloc[0], **pre_slope(g)} for s, g in m.groupby("site")]
    return pd.DataFrame(rows).sort_values("pct_per_year").reset_index(drop=True)


# --- seasonality ---------------------------------------------------------------------


def month_profile(m: pd.DataFrame) -> pd.DataFrame:
    """Calendar-month effect per site, % vs the site's average month, after removing a
    linear trend (pre-period, COVID months dropped)."""
    rows = []
    for site, g in m.groupby("site"):
        g = pre_months(g).sort_values("period")
        t = (g["period"] - PRE_START).dt.days.to_numpy() / 365.25
        y = np.log(g["questions"].clip(lower=1).to_numpy())
        resid = y - np.polyval(np.polyfit(t, y, 1), t)
        eff = pd.Series(resid).groupby(g["period"].dt.month.to_numpy()).mean()
        eff -= eff.mean()
        for month, e in eff.items():
            rows.append({"site": site, "group": g["group"].iloc[0], "month": month, "effect": e})
    out = pd.DataFrame(rows)
    out["pct"] = 100 * (np.exp(out["effect"]) - 1)
    return out


def weekday_shares(start: str, end: str) -> pd.DataFrame:
    """Share of each site's questions posted on each weekday (UTC), between two dates."""
    con = connect()
    df = con.execute(
        f"""
        SELECT site, isodow(CreationDate) AS dow, count(*) AS n
        FROM posts
        WHERE PostTypeId = 1 AND CreationDate >= '{start}' AND CreationDate < '{end}'
        GROUP BY 1, 2
        """
    ).df()
    df["share"] = df["n"] / df.groupby("site")["n"].transform("sum")
    df["group"] = df["site"].map(config.site_group)
    return df


def holiday_ratios(w: pd.DataFrame, years=range(2017, 2022)) -> pd.DataFrame:
    """Questions in the weeks containing 25 Dec and 1 Jan, relative to the mean of the
    four weeks starting 5, 4, 3 and 2 weeks before the Christmas week."""
    rows = []
    for site, g in w.groupby("site"):
        s = g.set_index("period")["questions"]
        for y in years:
            xmas = pd.Timestamp(f"{y}-12-25").to_period("W-SUN").start_time
            ny = pd.Timestamp(f"{y + 1}-01-01").to_period("W-SUN").start_time
            base = s.reindex([xmas - pd.Timedelta(days=7 * k) for k in (5, 4, 3, 2)])
            if base.isna().any() or base.mean() == 0:
                continue
            rows.append(
                {
                    "site": site,
                    "group": g["group"].iloc[0],
                    "year": y,
                    "christmas": s.get(xmas, np.nan) / base.mean(),
                    "new_year": s.get(ny, np.nan) / base.mean(),
                }
            )
    return pd.DataFrame(rows)


# --- pre-period tracking -------------------------------------------------------------


def demeaned_logs(m: pd.DataFrame) -> pd.DataFrame:
    """Wide (period x site) log questions minus each site's pre-period mean."""
    wide = m.pivot(index="period", columns="site", values="questions").sort_index()
    logs = np.log(wide.clip(lower=1))
    pre = logs.loc[PRE_START:PRE_END]
    return logs - pre.mean()


def tracking(m: pd.DataFrame) -> dict:
    """How the equal-weight donor average tracks Stack Overflow before the break, and how
    each donor's month-to-month changes co-move with Stack Overflow's (deseasonalised)."""
    d = demeaned_logs(m).loc[PRE_START:PRE_END]
    donors = [s for s in d.columns if config.site_group(s) == "donor"]
    gap = d[config.TREATED] - d[donors].mean(axis=1)
    keep = ~gap.index.to_series().between(*COVID)
    rmspe = float(np.sqrt((gap[keep] ** 2).mean()))
    # Deseasonalise with calendar-month means, then correlate monthly changes.
    des = d - d.groupby(d.index.month).transform("mean")
    diff = des.diff().loc[keep]
    corr = diff[donors].corrwith(diff[config.TREATED]).sort_values(ascending=False)
    return {
        "equal_weight_rmspe_log": rmspe,
        "gap_start_log": float(gap.iloc[:12].mean()),
        "gap_end_log": float(gap.iloc[-12:].mean()),
        "donor_change_corr": corr.round(3).to_dict(),
        "gap": gap,
    }


# --- figures -------------------------------------------------------------------------


def _style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e5e5e5", linewidth=0.8)
    ax.set_axisbelow(True)


def _shade(ax):
    ax.axvspan(*COVID, color="#cccccc", alpha=0.4, linewidth=0)
    ax.axvline(BREAK, color="#333333", linewidth=1, linestyle="--")


def fig_trends(m: pd.DataFrame, path) -> None:
    ix = indexed(m[m["period"] >= "2015-01-01"])
    gi = group_index(ix)
    fig, ax = plt.subplots(figsize=(10, 5.5))
    d = gi[gi["group"] == "donor"]
    ax.fill_between(d["period"], d["low"], d["high"], color=COLORS["donor"], alpha=0.15, lw=0)
    for g in GROUPS:
        s = gi[gi["group"] == g]
        ax.plot(s["period"], s["median"], color=COLORS[g], lw=2.4 if g == "treated" else 1.8)
        ax.annotate(
            LABELS[g].replace(" (15)", "") + ("" if g == "treated" else " (median)"),
            (s["period"].iloc[-1], s["median"].iloc[-1]),
            xytext=(6, 0),
            textcoords="offset points",
            color="#333333",
            fontsize=9,
            va="center",
        )
    _shade(ax)
    ax.set_yscale("log")
    ax.set_yticks([1, 3, 10, 30, 100, 200])
    ax.get_yaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.set_ylabel("Monthly questions, index (2019 average = 100), log scale")
    ax.set_title("Questions per month by site group, 2015–2026", loc="left", fontsize=12)
    ax.text(BREAK, 220, " ChatGPT\n (2022-11-30)", fontsize=8, va="top", color="#333333")
    ax.text(
        0.01,
        0.02,
        "Shaded band: range of the 15 comparison sites. Grey bar: COVID exclusion window.",
        transform=ax.transAxes,
        fontsize=8,
        color="#555555",
    )
    _style(ax)
    ax.set_xlim(pd.Timestamp("2015-01-01"), pd.Timestamp("2028-06-01"))
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_slopes(slopes: pd.DataFrame, path) -> None:
    s = slopes.sort_values("pct_per_year")
    fig, ax = plt.subplots(figsize=(8, 8))
    y = np.arange(len(s))
    for i, r in zip(y, s.itertuples(), strict=True):
        c = COLORS[r.group]
        ax.plot([r.low, r.high], [i, i], color=c, lw=1.5)
        ax.plot(r.pct_per_year, i, "o", color=c, ms=8 if r.group == "treated" else 6)
    ax.set_yticks(y, [short(x) for x in s["site"]], fontsize=8)
    ax.axvline(0, color="#999999", lw=0.8)
    so = s.loc[s["site"] == config.TREATED, "pct_per_year"].iloc[0]
    ax.axvline(so, color=COLORS["treated"], lw=0.8, ls=":")
    ax.set_xlabel("Change in monthly questions per year, 2017-01 to 2022-11 (%, 95% interval)")
    ax.set_title("Each site's trend before ChatGPT", loc="left", fontsize=12)
    handles = [
        plt.Line2D([], [], color=COLORS[g], marker="o", ls="", label=LABELS[g])
        for g in (*GROUPS, "context")
    ]
    ax.legend(handles=handles, fontsize=8, loc="lower right", frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_seasonality(wd: pd.DataFrame, mp: pd.DataFrame, path) -> None:
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.5))
    for g in GROUPS:
        s = wd[wd["group"] == g].groupby("dow")["share"].median()
        a1.plot(s.index, 100 * s.to_numpy(), "o-", color=COLORS[g], label=LABELS[g], ms=5)
        p = mp[mp["group"] == g].groupby("month")["pct"].median()
        a2.plot(p.index, p.to_numpy(), "o-", color=COLORS[g], ms=5)
    math = mp[mp["site"] == "math.stackexchange.com"].set_index("month")["pct"]
    a2.plot(math.index, math.to_numpy(), ls="--", color="#555555", lw=1.2, label="Mathematics")
    a1.axhline(100 / 7, color="#999999", lw=0.8)
    a1.set_xticks(range(1, 8), WEEKDAYS)
    a1.set_ylabel("% of the week's questions (UTC)")
    a1.set_title("Day of week, 2017-01 to 2022-11 (group medians)", loc="left", fontsize=10)
    a2.axhline(0, color="#999999", lw=0.8)
    a2.set_xticks(range(1, 13), list("JFMAMJJASOND"))
    a2.set_ylabel("% vs the site's average month (trend removed)")
    a2.set_title("Month of year, same period", loc="left", fontsize=10)
    a1.legend(fontsize=8, frameon=False)
    a2.legend(fontsize=8, frameon=False, loc="lower left")
    for a in (a1, a2):
        _style(a)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_tracking(m: pd.DataFrame, path) -> None:
    d = demeaned_logs(m).loc[PRE_START:PRE_END]
    donors = [s for s in d.columns if config.site_group(s) == "donor"]
    fig, ax = plt.subplots(figsize=(10, 5))
    for s in donors:
        ax.plot(d.index, d[s], color=COLORS["donor"], alpha=0.25, lw=0.9)
    avg = d[donors].mean(axis=1)
    ax.plot(
        d.index, avg, color=COLORS["donor"], lw=2, label="Comparison sites, equal-weight average"
    )
    ax.plot(d.index, d[config.TREATED], color=COLORS["treated"], lw=2.4, label="Stack Overflow")
    ax.axvspan(*COVID, color="#cccccc", alpha=0.4, linewidth=0)
    ax.axhline(0, color="#999999", lw=0.8)
    ax.set_ylabel("log monthly questions minus the site's 2017–2022 mean")
    ax.set_title(
        "Before ChatGPT: Stack Overflow vs the comparison sites (thin lines: each site)",
        loc="left",
        fontsize=12,
    )
    ax.legend(fontsize=9, frameon=False, loc="lower left")
    _style(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# --- run -----------------------------------------------------------------------------


def run() -> dict:
    fig_dir = config.FIGURE_DIR
    fig_dir.mkdir(parents=True, exist_ok=True)
    m = load_month()
    w = load_week()

    fig_trends(m, fig_dir / "eda_trends_indexed.png")
    slopes = pre_slopes(m)
    fig_slopes(slopes, fig_dir / "eda_pre_slopes.png")
    wd_pre = weekday_shares("2017-01-01", "2022-12-01")
    wd_post = weekday_shares("2025-01-01", "2026-10-01")
    mp = month_profile(m)
    fig_seasonality(wd_pre, mp, fig_dir / "eda_seasonality.png")
    fig_tracking(m, fig_dir / "eda_pre_tracking.png")
    hol = holiday_ratios(w)
    tr = tracking(m)

    gi = group_index(indexed(m))
    last = gi[gi["period"] == gi["period"].max()]
    so_prof = mp[mp["site"] == config.TREATED].set_index("month")["pct"]
    donor_prof = mp[mp["group"] == "donor"].groupby("month")["pct"].median()

    def weekend(df: pd.DataFrame) -> pd.Series:
        per_site = df[df["dow"] >= 6].groupby("site")["share"].sum()
        return per_site.groupby(df.groupby("site")["group"].first()).median()

    summary = {
        "index_2019_100_latest_full_month": {
            str(r.group): round(r.median, 2) for r in last.itertuples()
        },
        "latest_full_month": str(last["period"].iloc[0].date()),
        "pre_slopes_pct_per_year": slopes.round(2).to_dict(orient="records"),
        "so_slope_rank_among_donors": int(
            (
                slopes.loc[slopes.group == "donor", "pct_per_year"]
                < slopes.loc[slopes.site == config.TREATED, "pct_per_year"].iloc[0]
            ).sum()
        ),
        "weekend_share_pre": weekend(wd_pre).round(4).to_dict(),
        "weekend_share_2025_26": weekend(wd_post).round(4).to_dict(),
        "so_month_profile_pct": so_prof.round(1).to_dict(),
        "donor_month_profile_pct": donor_prof.round(1).to_dict(),
        "so_vs_donor_month_profile_corr": round(float(so_prof.corr(donor_prof)), 3),
        "holiday_ratio_median": hol.groupby("group")[["christmas", "new_year"]]
        .median()
        .round(3)
        .to_dict(orient="index"),
        **{k: v for k, v in tr.items() if k != "gap"},
    }
    qa = config.REPO_ROOT / "report" / "qa"
    qa.mkdir(parents=True, exist_ok=True)
    (qa / "eda_summary.json").write_text(json.dumps(summary, indent=2, default=float))
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=float))
