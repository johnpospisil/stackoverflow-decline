"""P22: newcomer pipeline (H4; PREREGISTRATION.md section 6 and deviation 2026-10-21).

(a) Synthetic control (section 4 setup) on log(first-time askers / questions), monthly, per site;
    first-time asker = question that is the asker's first post on the site (deleted owners
    excluded from numerator and denominator). Also ATTs for first-time askers and questions.
(b) Kaplan-Meier probability of a second post within 91 / 365 days for users whose first Stack
    Overflow post is a question: 2023-01..2026-09 arrivals vs 2019-01..2021-12, plus the
    Staging Ground split (2023-01..2024-05, 2024-06..). Greenwood standard errors.
Descriptive: first-time askers by account age at first post (<= 7 days vs older), return
rates by arrival quarter and account type, retention heatmap.

Usage: python -m sod.models.newcomers
"""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from sod import config, progress  # noqa: E402
from sod.db import connect  # noqa: E402
from sod.models import synth as sc  # noqa: E402

JOB = "newcomers"
CUTOFF = pd.Timestamp("2026-10-01")  # exclusive
HORIZONS = (91, 365)
NEW_ACCOUNT_DAYS = 7
GROUPS = {
    "2019-2021": ("2019-01-01", "2022-01-01"),
    "2023-2026": ("2023-01-01", "2026-10-01"),
    "2023-01..2024-05": ("2023-01-01", "2024-06-01"),
    "2024-06..2026-09 (Staging Ground)": ("2024-06-01", "2026-10-01"),
}
QA = config.REPO_ROOT / "report" / "qa"
TABLES = config.REPO_ROOT / "report" / "tables"


# --- (a) ----------------------------------------------------------------------------------


def first_time_panel() -> pd.DataFrame:
    con = connect()
    return (
        con.execute(
            f"""
        SELECT site, date_trunc('month', CreationDate)::DATE AS period,
               count(*) FILTER (WHERE NOT owner_deleted) AS questions_known_owner,
               count(*) FILTER (WHERE asker_first_post AND NOT owner_deleted) AS first_time,
               count(*) FILTER (WHERE asker_first_post AND NOT owner_deleted
                                AND asker_account_age_days <= {NEW_ACCOUNT_DAYS})
                   AS first_time_new_account,
               count(*) FILTER (WHERE asker_first_post AND NOT owner_deleted
                                AND asker_account_age_days > {NEW_ACCOUNT_DAYS})
                   AS first_time_older_account
        FROM read_parquet('{config.PARQUET_DIR}/questions/*/*.parquet')
        WHERE CreationDate >= DATE '2015-01-01' AND CreationDate < DATE '{CUTOFF.date()}'
        GROUP BY 1, 2
        """
        )
        .df()
        .assign(period=lambda d: pd.to_datetime(d["period"]))
    )


def synth_on(L: pd.DataFrame) -> dict:
    L = L.loc[sc.START : sc.END]
    pre, post = sc.masks(L.index)
    D = sc.demean(L, pre)
    main = sc.synth(D, sc.TREATED, sc.DONORS, pre, post)
    _, ci = sc.pysyncon_fit_and_ci(D, pre, post)
    ps = sc.placebo_space(D, pre, post)
    return {
        "att_pct": float(sc.pct(main["att_log"])),
        "att_log": main["att_log"],
        "ci_pct": [float(sc.pct(ci["lower_ci"].mean())), float(sc.pct(ci["upper_ci"].mean()))],
        "months_excluding_zero": int((ci["upper_ci"] < 0).sum()),
        "rank": int(ps.loc[ps["site"] == sc.TREATED, "rank"].iloc[0]),
        "pre_rmspe": main["pre_rmspe"],
        "gap": main["gap"],
    }


# --- (b) Kaplan-Meier -----------------------------------------------------------------------


def km_at(durations: np.ndarray, events: np.ndarray, times=HORIZONS) -> dict:
    """Kaplan-Meier P(event by t) and Greenwood SE, for durations in days."""
    order = np.argsort(durations)
    d, e = durations[order], events[order].astype(bool)
    ut, idx = np.unique(d, return_index=True)
    n_at_risk = len(d) - idx
    deaths = np.add.reduceat(e.astype(float), idx)
    h = deaths / n_at_risk
    S = np.cumprod(1 - h)
    with np.errstate(divide="ignore", invalid="ignore"):
        gw = np.cumsum(
            np.where(n_at_risk > deaths, deaths / (n_at_risk * (n_at_risk - deaths)), 0.0)
        )
    out = {}
    for t in times:
        k = np.searchsorted(ut, t, side="right") - 1
        s = 1.0 if k < 0 else S[k]
        var = 0.0 if k < 0 else s**2 * gw[k]
        out[t] = {"p": float(1 - s), "se": float(np.sqrt(var))}
    out["n"] = int(len(d))
    return out


def askers() -> pd.DataFrame:
    con = connect()
    df = con.execute(
        f"""
        SELECT s.first_post_at, s.days_to_second_post,
               date_diff('millisecond', u.CreationDate, s.first_post_at) / 86400000.0
                   AS account_age_days
        FROM read_parquet('{config.PARQUET_DIR}/user_summary/*/*.parquet') s
        LEFT JOIN users u ON u.site = s.site AND u.Id = s.user_id
        WHERE s.site = '{config.TREATED}' AND s.first_post_type = 'question'
        """
    ).df()
    df["first_post_at"] = pd.to_datetime(df["first_post_at"])
    follow = (CUTOFF - df["first_post_at"]).dt.total_seconds() / 86400
    df["event"] = df["days_to_second_post"].notna() & (df["days_to_second_post"] <= follow)
    df["duration"] = np.where(df["event"], df["days_to_second_post"], follow)
    df["new_account"] = df["account_age_days"] <= NEW_ACCOUNT_DAYS
    return df


def km_groups(df: pd.DataFrame) -> dict:
    res = {}
    for name, (a, b) in GROUPS.items():
        g = df[(df["first_post_at"] >= a) & (df["first_post_at"] < b)]
        res[name] = km_at(g["duration"].to_numpy(), g["event"].to_numpy())
    base = res["2019-2021"]
    for name in list(GROUPS)[1:]:
        for t in HORIZONS:
            diff = res[name][t]["p"] - base[t]["p"]
            se = np.hypot(res[name][t]["se"], base[t]["se"])
            res[name][t]["diff_vs_2019_2021"] = float(diff)
            res[name][t]["diff_ci"] = [float(diff - 1.96 * se), float(diff + 1.96 * se)]
    return res


def km_by_quarter(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    q = df["first_post_at"].dt.to_period("Q")
    for (quarter, new), g in df.groupby([q, "new_account"]):
        if quarter < pd.Period("2015Q1"):
            continue
        r = km_at(g["duration"].to_numpy(), g["event"].to_numpy())
        follow_max = (CUTOFF - quarter.end_time).days
        rows.append(
            {
                "quarter": str(quarter),
                "new_account": bool(new),
                "n": r["n"],
                "p91": r[91]["p"] if follow_max >= 91 else np.nan,
                "p365": r[365]["p"] if follow_max >= 365 else np.nan,
            }
        )
    return pd.DataFrame(rows)


# --- figures -----------------------------------------------------------------------------------


def fig_first_time(panel: pd.DataFrame, path) -> None:
    so = panel[panel["site"] == sc.TREATED].set_index("period").sort_index().loc["2015":]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(so.index, so["questions_known_owner"], color="#999999", lw=1.5, label="All questions")
    ax.plot(
        so.index,
        so["first_time_new_account"],
        color="#D55E00",
        lw=2,
        label=f"First-time askers, new account (≤ {NEW_ACCOUNT_DAYS} days)",
    )
    ax.plot(
        so.index,
        so["first_time_older_account"],
        color="#0072B2",
        lw=2,
        label="First-time askers, older account",
    )
    ax.axvline(pd.Timestamp(config.BREAK_DATE), color="#333333", lw=1, ls=":")
    ax.axvline(pd.Timestamp("2024-06-04"), color="#999999", lw=1, ls="--")
    ax.text(
        pd.Timestamp("2024-06-04"),
        0.97,
        " Staging\n Ground",
        fontsize=8,
        va="top",
        transform=ax.get_xaxis_transform(),
    )
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_ylabel("Per month (log scale)")
    ax.set_title(
        "Stack Overflow: first-time askers by account age at their first question",
        loc="left",
        fontsize=11,
    )
    ax.legend(fontsize=8, frameon=False, loc="lower left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e5e5e5")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_return(byq: pd.DataFrame, path) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.5))
    for new, c, lab in ((True, "#D55E00", "new account"), (False, "#0072B2", "older account")):
        d = byq[byq["new_account"] == new]
        x = pd.PeriodIndex(d["quarter"], freq="Q").to_timestamp()
        ax.plot(x, 100 * d["p365"], color=c, lw=2, label=f"Within 12 months, {lab}")
        ax.plot(x, 100 * d["p91"], color=c, lw=1.2, ls="--", label=f"Within 3 months, {lab}")
    ax.axvline(pd.Timestamp(config.BREAK_DATE), color="#333333", lw=1, ls=":")
    ax.axvline(pd.Timestamp("2024-06-04"), color="#999999", lw=1, ls="--")
    ax.set_ylabel("% making a second post (Kaplan–Meier)")
    ax.set_xlabel("Quarter of first question")
    ax.set_title("Do first-time askers come back?", loc="left", fontsize=11)
    ax.legend(fontsize=8, frameon=False, ncol=2)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e5e5e5")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_heatmap(path, max_k: int = 24) -> None:
    ca = pd.read_parquet(config.PARQUET_DIR / "cohort_activity" / f"site={sc.TREATED}")
    ca["cohort_month"] = pd.to_datetime(ca["cohort_month"])
    ca = ca[(ca["cohort_month"] >= "2015-01-01") & ca["months_since"].between(1, max_k)]
    ca["share"] = ca["active"] / ca["cohort_size"]
    grid = ca.pivot(index="cohort_month", columns="months_since", values="share")
    last = pd.Timestamp("2026-09-01")
    for c in grid.index:  # blank cells not yet observed
        k_obs = (last.year - c.year) * 12 + last.month - c.month
        grid.loc[c, grid.columns > k_obs] = np.nan
    fig, ax = plt.subplots(figsize=(9, 7))
    im = ax.imshow(
        100 * grid.to_numpy(),
        aspect="auto",
        cmap="Blues",
        vmin=0,
        vmax=np.nanpercentile(100 * grid.to_numpy(), 99),
    )
    years = [i for i, d in enumerate(grid.index) if d.month == 1]
    ax.set_yticks(years, [grid.index[i].year for i in years])
    ax.set_xticks(range(0, max_k, 3), range(1, max_k + 1, 3))
    ax.set_xlabel("Months since first post")
    ax.set_ylabel("Month of first post (cohort)")
    ax.set_title("Share of each newcomer cohort posting again, by month", loc="left", fontsize=11)
    fig.colorbar(im, ax=ax, label="% of cohort active")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# --- run ---------------------------------------------------------------------------------------


def run() -> dict:
    progress.write_manifest(JOB, {"panel": 3, "synth": 3, "km": 3, "write": 1})

    def step(name, fn):
        rep = progress.Reporter(JOB, name, 1)
        out = fn()
        rep.finish(1)
        return out

    panel = step("panel", first_time_panel)

    def synths():
        w = panel.pivot(
            index="period", columns="site", values=["first_time", "questions_known_owner"]
        )
        ft = w["first_time"].clip(lower=0.5)
        q = w["questions_known_owner"].clip(lower=1)
        return {
            "log_share_first_time": synth_on(np.log(ft / q)),
            "first_time_askers": synth_on(np.log(ft)),
            "questions": synth_on(np.log(q)),
        }

    s = step("synth", synths)
    df = step("km", askers)
    km = km_groups(df)
    byq = km_by_quarter(df)

    def write():
        share = s["log_share_first_time"]
        a_ok = share["att_log"] < 0 and share["ci_pct"][1] < 0
        b_ok = all(km["2023-2026"][t]["diff_ci"][1] < 0 for t in HORIZONS)
        so = panel[panel["site"] == sc.TREATED].set_index("period")
        yr = so.groupby(so.index.year)[
            [
                "questions_known_owner",
                "first_time",
                "first_time_new_account",
                "first_time_older_account",
            ]
        ].sum()
        summary = {
            "a_synth": {k: {kk: vv for kk, vv in v.items() if kk != "gap"} for k, v in s.items()},
            "a_supported": bool(a_ok),
            "b_km": {g: {str(k): v for k, v in r.items()} for g, r in km.items()},
            "b_supported": bool(b_ok),
            "h4_supported": bool(a_ok and b_ok),
            "so_by_year": yr.loc[[2019, 2021, 2023, 2024, 2025, 2026]]
            .astype(int)
            .to_dict(orient="index"),
        }
        byq.to_csv(TABLES / "newcomers_return_by_quarter.csv", index=False)
        (QA / "newcomers_summary.json").write_text(json.dumps(summary, indent=2, default=float))
        fig_first_time(panel, config.FIGURE_DIR / "newcomers_first_time_askers.png")
        fig_return(byq, config.FIGURE_DIR / "newcomers_return_rates.png")
        fig_heatmap(config.FIGURE_DIR / "newcomers_retention_heatmap.png")
        return summary

    return step("write", write)


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=float))
