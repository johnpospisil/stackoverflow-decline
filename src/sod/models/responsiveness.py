"""P24: responsiveness over time (exploratory E1).

Fixed-window measures from the P13 panels (a question counts only if its whole window ends
before the 2026-09-30 cut-off): answered within 24 h, answered within 7 days, accepted within
30 days. Weekly Stack Overflow series with 95% Wilson bands; monthly comparison with the other
site groups. Speed: median hours to first answer among questions answered within 7 days (a
conditional measure that is comparable across time, unlike the raw median, which is
censored for recent questions). Capacity: active answerers and answers per 100 questions.

Usage: python -m sod.models.responsiveness
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

JOB = "responsiveness"
START = pd.Timestamp("2017-01-01")
MEASURES = {
    "answered_24h": ("eligible_24h", "Answered within 24 hours"),
    "answered_7d": ("eligible_7d", "Answered within 7 days"),
    "accepted_30d": ("eligible_30d", "Answer accepted within 30 days"),
}
GROUP_COLORS = {
    "treated": "#D55E00",
    "so_language": "#E69F00",
    "tech_exposed": "#0072B2",
    "donor": "#009E73",
}
GROUP_LABELS = {
    "treated": "Stack Overflow",
    "so_language": "SO in other languages (median)",
    "tech_exposed": "Other tech sites (median)",
    "donor": "Comparison sites (median)",
}
QA = config.REPO_ROOT / "report" / "qa"
TABLES = config.REPO_ROOT / "report" / "tables"


def wilson(k: np.ndarray, n: np.ndarray, z: float = 1.96) -> tuple[np.ndarray, np.ndarray]:
    n = np.asarray(n, float)
    with np.errstate(divide="ignore", invalid="ignore"):  # empty weeks give NaN
        p = np.divide(k, n, out=np.full(len(n), np.nan), where=n > 0)
        denom = 1 + z**2 / n
        centre = (p + z**2 / (2 * n)) / denom
        half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return centre - half, centre + half


def conditional_speed() -> pd.DataFrame:
    """Monthly median hours to first answer among questions answered within 7 days, eligible
    for the 7-day window (Stack Overflow)."""
    con = connect()
    return (
        con.execute(
            f"""
        SELECT date_trunc('month', CreationDate)::DATE AS period,
               median(hours_to_first_answer) AS median_hours_if_answered_7d,
               quantile_cont(hours_to_first_answer, 0.75) AS p75_hours_if_answered_7d,
               count(*) AS n
        FROM read_parquet('{config.PARQUET_DIR}/questions/*/*.parquet')
        WHERE site = '{config.TREATED}' AND CreationDate >= DATE '{START.date()}'
          AND CreationDate < TIMESTAMP '2026-10-01' - INTERVAL 7 DAY
          AND hours_to_first_answer <= 168
        GROUP BY 1 ORDER BY 1
        """
        )
        .df()
        .assign(period=lambda d: pd.to_datetime(d["period"]))
    )


def answer_age() -> pd.DataFrame:
    """Per year: share of Stack Overflow answers posted within 7 days of their question, and
    share going to questions more than a year old."""
    con = connect()
    return con.execute(
        f"""
        WITH a AS (SELECT ParentId, CreationDate FROM posts
                   WHERE site = '{config.TREATED}' AND PostTypeId = 2
                     AND CreationDate >= DATE '{START.date()}'),
             q AS (SELECT Id, CreationDate AS qd FROM posts
                   WHERE site = '{config.TREATED}' AND PostTypeId = 1)
        SELECT year(a.CreationDate) AS year, count(*) AS answers,
               avg(((a.CreationDate - q.qd) <= INTERVAL 7 DAY)::INT) AS within_7d_of_question,
               avg(((a.CreationDate - q.qd) > INTERVAL 365 DAY)::INT) AS to_questions_over_1y
        FROM a JOIN q ON q.Id = a.ParentId
        GROUP BY 1 ORDER BY 1
        """
    ).df()


def group_monthly(m: pd.DataFrame) -> pd.DataFrame:
    m = m.copy()
    for k, (n, _) in MEASURES.items():
        m[f"rate_{k}"] = m[k] / m[n].where(m[n] > 0)
    m["answers_per_100q"] = 100 * m["answers"] / m["questions"].where(m["questions"] > 0)
    m["answerers_per_100q"] = 100 * m["active_answerers"] / m["questions"].where(m["questions"] > 0)
    cols = [c for c in m.columns if c.startswith("rate_")] + [
        "answers_per_100q",
        "answerers_per_100q",
    ]
    return m.groupby(["group", "period"])[cols].median().reset_index()


# --- figures -------------------------------------------------------------------------------


def fig_so(w: pd.DataFrame, speed: pd.DataFrame, path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    for ax, (k, (n, label)) in zip(axes.flat[:3], MEASURES.items(), strict=False):
        d = w[w[n] > 0]
        lo, hi = wilson(d[k].to_numpy(), d[n].to_numpy())
        ax.fill_between(d["period"], 100 * lo, 100 * hi, color="#D55E00", alpha=0.2, lw=0)
        ax.plot(d["period"], 100 * d[k] / d[n], color="#D55E00", lw=1)
        ax.set_title(f"{label} (% of questions, weekly, 95% band)", loc="left", fontsize=10)
    ax = axes.flat[3]
    ax.plot(
        speed["period"],
        speed["median_hours_if_answered_7d"],
        color="#0072B2",
        lw=1.8,
        label="median",
    )
    ax.plot(
        speed["period"],
        speed["p75_hours_if_answered_7d"],
        color="#0072B2",
        lw=1,
        ls="--",
        label="75th percentile",
    )
    ax.set_title(
        "Hours to first answer, among questions answered within 7 days", loc="left", fontsize=10
    )
    ax.legend(fontsize=8, frameon=False)
    for ax in axes.flat:
        ax.axvline(pd.Timestamp(config.BREAK_DATE), color="#333333", lw=1, ls=":")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#e5e5e5")
    fig.suptitle(
        "Stack Overflow responsiveness, 2017–2026 (fixed windows; questions too close "
        "to the cut-off are excluded)",
        x=0.01,
        ha="left",
        fontsize=11,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_groups(g: pd.DataFrame, path) -> None:
    panels = [
        ("rate_answered_24h", "Answered within 24 hours (%)", 100),
        ("rate_accepted_30d", "Accepted within 30 days (%)", 100),
        ("answerers_per_100q", "Active answerers per 100 questions", 1),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    for ax, (col, title, scale) in zip(axes, panels, strict=True):
        for grp, c in GROUP_COLORS.items():
            d = g[(g["group"] == grp) & (g["period"] >= START)]
            ax.plot(
                d["period"],
                scale * d[col],
                color=c,
                lw=2.2 if grp == "treated" else 1.4,
                label=GROUP_LABELS[grp],
            )
        ax.axvline(pd.Timestamp(config.BREAK_DATE), color="#333333", lw=1, ls=":")
        ax.set_title(title, loc="left", fontsize=10)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#e5e5e5")
    axes[0].legend(fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# --- run -------------------------------------------------------------------------------------


def run() -> dict:
    progress.write_manifest(JOB, {"load": 1, "speed": 2, "write": 1})
    rep = progress.Reporter(JOB, "load", 1)
    w = pd.read_parquet(config.PANEL_DIR / "site_week.parquet")
    w = w[(w["site"] == config.TREATED) & (w["period"] >= START) & ~w["partial_period"]]
    m = pd.read_parquet(config.PANEL_DIR / "site_month.parquet")
    m = m[~m["partial_period"]].assign(group=lambda d: d["site"].map(config.site_group))
    rep.finish(1)
    rep = progress.Reporter(JOB, "speed", 1)
    speed = conditional_speed()
    rep.finish(1)
    rep = progress.Reporter(JOB, "write", 1)
    g = group_monthly(m)

    def year_avg(col, grp, years):
        d = g[(g["group"] == grp) & g["period"].dt.year.isin(years)]
        return float(d[col].mean())

    periods = {
        "2019-2021": [2019, 2020, 2021],
        "2023": [2023],
        "2024": [2024],
        "2025": [2025],
        "2026": [2026],
    }
    table = {
        grp: {
            col: {p: year_avg(col, grp, ys) for p, ys in periods.items()}
            for col in (
                "rate_answered_24h",
                "rate_answered_7d",
                "rate_accepted_30d",
                "answerers_per_100q",
                "answers_per_100q",
            )
        }
        for grp in GROUP_COLORS
    }
    sp = speed.groupby(speed["period"].dt.year)["median_hours_if_answered_7d"].median()
    age = answer_age()
    age.round(4).to_csv(TABLES / "answer_age_by_year.csv", index=False)
    summary = {
        "by_group_and_period": table,
        "so_median_hours_if_answered_7d_by_year": {int(k): float(v) for k, v in sp.items()},
        "answer_age_by_year": age.round(4).to_dict(orient="records"),
        "weeks_used": int(len(w)),
        "last_week_with_24h_window": str(w.loc[w["eligible_24h"] > 0, "period"].max().date()),
        "last_week_with_30d_window": str(w.loc[w["eligible_30d"] > 0, "period"].max().date()),
    }
    rows = [
        {"group": grp, "measure": col, "period": p, "value": v}
        for grp, cols in table.items()
        for col, ps in cols.items()
        for p, v in ps.items()
    ]
    pd.DataFrame(rows).round(4).to_csv(TABLES / "responsiveness.csv", index=False)
    (QA / "responsiveness_summary.json").write_text(json.dumps(summary, indent=2))
    fig_so(w, speed, config.FIGURE_DIR / "responsiveness_so.png")
    fig_groups(g, config.FIGURE_DIR / "responsiveness_groups.png")
    rep.finish(1)
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
