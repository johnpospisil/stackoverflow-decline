"""P23: answerers (H5; PREREGISTRATION.md section 6 and deviation 2026-10-21 "H5 placebo cohorts").

Primary: for each 3-year window W (2014-16 ... 2021-23), core answerers are the top 1% of that
window's answerers by answer count. Outcome: share of them active (>= 1 answer) 1, 2 and 3
years after W ends. Windows ending 2016-2019 are the pre-ChatGPT reference cohorts; H5 is
supported if the 2019-21 cohort's share at distances 2 and 3 (2023, 2024) is below the lowest
reference cohort at the same distance. Windows 2020-22 and 2021-23 are shown as partly treated.
Original version (labelled): share of 2019-21 core active each year 2017-2026 vs the 2017-2021
trend line extended, with a 95% prediction interval.
Descriptive: answers per active core answerer, the core's share of all answers, the share of
each year's top-1% answerers who are recent arrivals (first answer in the previous 24 months).
Comparison: the same cohort design on Mathematics, Physics and the donor median.

Usage: python -m sod.models.answerers
"""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.api as sm  # noqa: E402

from sod import config, progress  # noqa: E402
from sod.db import connect  # noqa: E402

JOB = "answerers"
WINDOWS = [(y, y + 2) for y in range(2014, 2022)]  # 2014-16 ... 2021-23
REFERENCE_ENDS = (2016, 2017, 2018, 2019)
TREATED_WINDOW = (2019, 2021)
DISTANCES = (1, 2, 3)
LAST_FULL_YEAR = 2025
CORE_SHARE = 0.01
COMPARE = ("math.stackexchange.com", "physics.stackexchange.com")
QA = config.REPO_ROOT / "report" / "qa"
TABLES = config.REPO_ROOT / "report" / "tables"


def yearly_answers(sites) -> pd.DataFrame:
    con = connect()
    in_list = ", ".join(f"'{s}'" for s in sites)
    return con.execute(
        f"""
        SELECT site, user_id, year(month) AS year, sum(n_answers)::BIGINT AS answers
        FROM read_parquet('{config.PARQUET_DIR}/user_months/*/*.parquet')
        WHERE site IN ({in_list}) AND n_answers > 0
        GROUP BY ALL
        """
    ).df()


def core_set(ya: pd.DataFrame, start: int, end: int) -> set:
    w = ya[(ya["year"] >= start) & (ya["year"] <= end)].groupby("user_id")["answers"].sum()
    n = int(np.ceil(CORE_SHARE * len(w)))
    return set(w.sort_values(ascending=False, kind="stable").index[:n])


def cohort_table(ya: pd.DataFrame) -> pd.DataFrame:
    """One row per window x distance: core size, active count, share active."""
    active = {y: set(g["user_id"]) for y, g in ya.groupby("year")}
    rows = []
    for start, end in WINDOWS:
        core = core_set(ya, start, end)
        for d in DISTANCES:
            year = end + d
            if year > LAST_FULL_YEAR:
                continue
            n_act = len(core & active.get(year, set()))
            rows.append(
                {
                    "window": f"{start}-{str(end)[2:]}",
                    "end": end,
                    "distance": d,
                    "year": year,
                    "core": len(core),
                    "active": n_act,
                    "share": n_act / len(core),
                }
            )
    return pd.DataFrame(rows)


def h5_test(ct: pd.DataFrame) -> dict:
    ref = ct[ct["end"].isin(REFERENCE_ENDS)]
    tr = ct[ct["end"] == TREATED_WINDOW[1]]
    out = {}
    for d in (2, 3):
        r = ref[ref["distance"] == d]["share"]
        t = float(tr.loc[tr["distance"] == d, "share"].iloc[0])
        out[f"distance_{d}"] = {
            "treated_share": t,
            "reference_min": float(r.min()),
            "reference_max": float(r.max()),
            "below_range": bool(t < r.min()),
        }
    out["supported"] = all(v["below_range"] for v in out.values())
    return out


def original_version(ya: pd.DataFrame) -> dict:
    core = core_set(ya, *TREATED_WINDOW)
    years = range(2017, LAST_FULL_YEAR + 1)
    act = {y: len(core & set(ya.loc[ya["year"] == y, "user_id"])) / len(core) for y in years}
    s = pd.Series(act)
    pre = s.loc[2017:2021]
    fit = sm.OLS(pre.to_numpy(), sm.add_constant(np.array(pre.index, float))).fit()
    post_years = np.array(range(2023, LAST_FULL_YEAR + 1), float)
    pred = fit.get_prediction(sm.add_constant(post_years)).summary_frame(alpha=0.05)
    rows = {
        int(y): {
            "share": float(s[int(y)]),
            "trend": float(p),
            "pi_low": float(lo),
            "below_pi": bool(s[int(y)] < lo),
        }
        for y, p, lo in zip(post_years, pred["mean"], pred["obs_ci_lower"], strict=True)
    }
    return {
        "share_by_year": {int(k): float(v) for k, v in s.items()},
        "post": rows,
        "supported": all(r["below_pi"] for r in rows.values()),
    }


def core_activity(site: str) -> pd.DataFrame:
    ac = pd.read_parquet(config.PARQUET_DIR / "answer_concentration" / f"site={site}")
    ac = ac.sort_values("year")
    ac["answers_per_active_core"] = (
        ac["answers"] * ac["core_answer_share"] / ac["core_answerers_active"].clip(lower=1)
    )
    return ac


def emerging(ya: pd.DataFrame) -> pd.DataFrame:
    """Share of each year's top-1% answerers whose first answer was in the previous 24 months
    (first answer year >= year - 1)."""
    first = ya.groupby("user_id")["year"].min()
    rows = []
    for y, g in ya.groupby("year"):
        if y < 2012 or y > LAST_FULL_YEAR:
            continue
        n = int(np.ceil(CORE_SHARE * len(g)))
        top = g.sort_values("answers", ascending=False, kind="stable")["user_id"].iloc[:n]
        recent = (first.loc[top] >= y - 1).mean()
        rows.append({"year": int(y), "top1pct": n, "share_recent_arrivals": float(recent)})
    return pd.DataFrame(rows)


# --- figures -----------------------------------------------------------------------------


def fig_cohorts(tables: dict, path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), sharey=True)
    for ax, (site, ct) in zip(axes, tables.items(), strict=True):
        for w, g in ct.groupby("window", sort=False):
            end = g["end"].iloc[0]
            if end in REFERENCE_ENDS:
                c, lw, ls = "#999999", 1.2, "-"
            elif end == TREATED_WINDOW[1]:
                c, lw, ls = "#D55E00", 2.4, "-"
            else:
                c, lw, ls = "#E69F00", 1.4, "--"
            ax.plot(g["distance"], 100 * g["share"], "o-", color=c, lw=lw, ls=ls, ms=4)
            ax.annotate(
                w,
                (g["distance"].iloc[-1], 100 * g["share"].iloc[-1]),
                fontsize=7,
                color=c,
                xytext=(4, 0),
                textcoords="offset points",
                va="center",
            )
        ax.set_xticks(DISTANCES, [f"+{d} yr" for d in DISTANCES])
        ax.set_xlim(0.8, 3.6)
        ax.set_title(
            site.replace(".stackexchange.com", "").replace(".com", ""), loc="left", fontsize=10
        )
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#e5e5e5")
    axes[0].set_ylabel("% of the window's top-1% answerers still answering")
    fig.suptitle(
        "Core answerers still active after their window "
        "(grey: pre-ChatGPT windows; orange: 2019–21; dashed: partly treated)",
        x=0.01,
        ha="left",
        fontsize=11,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_core(ac: pd.DataFrame, em: pd.DataFrame, path) -> None:
    ac = ac[(ac["year"] >= 2012) & (ac["year"] <= LAST_FULL_YEAR)]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    axes[0].plot(ac["year"], ac["core_answerers_active"], "o-", color="#0072B2")
    axes[0].set_title("2019–21 core answerers active (count)", loc="left", fontsize=10)
    axes[1].plot(ac["year"], 100 * ac["core_answer_share"], "o-", color="#0072B2")
    axes[1].set_title("Their share of all answers (%)", loc="left", fontsize=10)
    axes[2].plot(em["year"], 100 * em["share_recent_arrivals"], "o-", color="#0072B2")
    axes[2].set_title(
        "Top-1% answerers who started in the last 2 years (%)", loc="left", fontsize=10
    )
    for ax in axes:
        ax.axvline(2022.9, color="#333333", lw=1, ls=":")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#e5e5e5")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# --- run ---------------------------------------------------------------------------------


def run() -> dict:
    sites = [config.TREATED, *config.SITE_GROUPS["donor"]]
    progress.write_manifest(JOB, {"load": 2, "cohorts": len(sites), "write": 1})
    rep = progress.Reporter(JOB, "load", 1)
    ya_all = yearly_answers(sites)
    rep.finish(len(ya_all))

    rep = progress.Reporter(JOB, "cohorts", len(sites))
    tables, tests = {}, {}
    for i, site in enumerate(sites, start=1):
        ct = cohort_table(ya_all[ya_all["site"] == site])
        tables[site], tests[site] = ct, h5_test(ct)
        rep.update(i, i)
    rep.finish(len(sites))

    rep = progress.Reporter(JOB, "write", 1)
    so = ya_all[ya_all["site"] == config.TREATED]
    ac = core_activity(config.TREATED)
    em = emerging(so)
    donors = config.SITE_GROUPS["donor"]
    so_ct = tables[config.TREATED]
    ratio = lambda ct: float(  # noqa: E731
        ct.loc[(ct["end"] == 2021) & (ct["distance"] == 3), "share"].iloc[0]
        / ct.loc[(ct["end"].isin(REFERENCE_ENDS)) & (ct["distance"] == 3), "share"].mean()
    )
    summary = {
        "so_cohorts": so_ct.round(4).to_dict(orient="records"),
        "h5_test": tests[config.TREATED],
        "h5_supported": tests[config.TREATED]["supported"],
        "original_version": original_version(so),
        "donors_supported_count": int(sum(tests[d]["supported"] for d in donors)),
        "distance3_ratio_2019_21_vs_reference_mean": {
            "stackoverflow": ratio(so_ct),
            "donor_median": float(np.median([ratio(tables[d]) for d in donors])),
            **{c.split(".")[0]: ratio(tables[c]) for c in COMPARE},
        },
        "core_activity": ac[
            [
                "year",
                "answerers",
                "answers",
                "core_answerers_active",
                "core_answer_share",
                "answers_per_active_core",
                "gini",
                "top1pct_share",
            ]
        ]
        .round(4)
        .to_dict(orient="records"),
        "emerging_top_answerers": em.round(4).to_dict(orient="records"),
    }
    pd.concat([t.assign(site=s) for s, t in tables.items()]).to_csv(
        TABLES / "answerer_cohorts.csv", index=False
    )
    (QA / "answerers_summary.json").write_text(json.dumps(summary, indent=2, default=float))
    fig_cohorts(
        {s: tables[s] for s in (config.TREATED, *COMPARE)},
        config.FIGURE_DIR / "answerers_cohorts.png",
    )
    fig_core(ac, em, config.FIGURE_DIR / "answerers_core.png")
    rep.finish(1)
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=float))
