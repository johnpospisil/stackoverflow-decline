"""P08: data-quality profile of the ingested Parquet.

Writes report/qa/quality.json (all check results), report/qa/weekly_anomalies.csv
and report/figures/qa_weekly_questions.png.

Usage: python -m sod.build.quality
"""

from __future__ import annotations

import json
import time
from datetime import timedelta

import numpy as np
import pandas as pd

from sod import config, events
from sod.db import connect

QA_DIR = config.REPORT_DIR / "qa"
EARLIEST = "2008-07-31"  # Stack Overflow's first public post
CHART_SITES = (
    config.TREATED,
    "math.stackexchange.com",
    "physics.stackexchange.com",
    "english.stackexchange.com",
)
ANOMALY_Z = 5.0
ROLLING_WEEKS = 13


def per_site(con, sql: str) -> dict[str, int]:
    return {site: int(n) for site, n in con.execute(sql).fetchall()}


def run_checks(con) -> dict:
    cutoff_end = (config.DUMP_CUTOFF + timedelta(days=1)).isoformat()
    con.execute(
        "CREATE TEMP TABLE q AS SELECT site, Id, CreationDate, AcceptedAnswerId, n_tags, tags "
        "FROM posts WHERE PostTypeId = 1"
    )
    con.execute(
        "CREATE TEMP TABLE a AS SELECT site, Id, ParentId, CreationDate FROM posts "
        "WHERE PostTypeId = 2"
    )
    c: dict[str, dict] = {}
    c["duplicate_post_ids"] = per_site(
        con, "SELECT site, count(*) - count(DISTINCT Id) FROM posts GROUP BY site"
    )
    c["orphan_answers"] = per_site(
        con,
        "SELECT a.site, count(*) FILTER (WHERE q.Id IS NULL) FROM a "
        "LEFT JOIN q ON a.site = q.site AND a.ParentId = q.Id GROUP BY a.site",
    )
    c["accepted_answer_missing"] = per_site(
        con,
        "SELECT q.site, count(*) FILTER (WHERE a.Id IS NULL) FROM q "
        "LEFT JOIN a ON q.site = a.site AND q.AcceptedAnswerId = a.Id "
        "WHERE q.AcceptedAnswerId IS NOT NULL GROUP BY q.site",
    )
    c["answer_before_question"] = per_site(
        con,
        "SELECT a.site, count(*) FILTER (WHERE a.CreationDate < q.CreationDate) FROM a "
        "JOIN q ON a.site = q.site AND a.ParentId = q.Id GROUP BY a.site",
    )
    c["posts_outside_date_range"] = per_site(
        con,
        f"SELECT site, count(*) FILTER (WHERE CreationDate < '{EARLIEST}' "
        f"OR CreationDate >= '{cutoff_end}') FROM posts GROUP BY site",
    )
    c["questions_without_tags"] = per_site(
        con, "SELECT site, count(*) FILTER (WHERE n_tags = 0) FROM q GROUP BY site"
    )
    c["questions_without_initial_tags_event"] = per_site(
        con,
        "SELECT q.site, count(*) FILTER (WHERE h.PostId IS NULL) FROM q "
        "LEFT JOIN (SELECT DISTINCT site, PostId FROM posthistory WHERE PostHistoryTypeId = 3) h "
        "ON q.site = h.site AND q.Id = h.PostId GROUP BY q.site",
    )
    for table in ("comments", "votes"):
        c[f"orphan_{table}"] = per_site(
            con,
            f"SELECT t.site, count(*) FILTER (WHERE p.Id IS NULL) FROM {table} t "
            "LEFT JOIN (SELECT site, Id FROM posts) p ON t.site = p.site AND t.PostId = p.Id "
            "GROUP BY t.site",
        )
    c["orphan_posthistory"] = per_site(
        con,
        "SELECT h.site, count(*) FILTER (WHERE p.Id IS NULL) FROM posthistory h "
        "LEFT JOIN (SELECT site, Id FROM posts) p ON h.site = p.site AND h.PostId = p.Id "
        "GROUP BY h.site",
    )
    c["duplicate_user_ids"] = per_site(
        con, "SELECT site, count(*) - count(DISTINCT Id) FROM users GROUP BY site"
    )
    c["question_owner_not_in_users"] = per_site(
        con,
        "SELECT p.site, count(*) FILTER (WHERE u.Id IS NULL) FROM posts p "
        "LEFT JOIN users u ON p.site = u.site AND p.OwnerUserId = u.Id "
        "WHERE p.PostTypeId = 1 AND p.OwnerUserId IS NOT NULL GROUP BY p.site",
    )
    return c


def tag_count_comparison(con) -> dict:
    """Tags.xml `Count` vs questions currently carrying the tag (Stack Overflow, top 300)."""
    df = con.execute(
        """
        WITH computed AS (
            SELECT tag, count(*) AS n FROM (SELECT unnest(tags) AS tag FROM q
            WHERE site = 'stackoverflow.com') GROUP BY tag
        )
        SELECT t.TagName AS tag, t."Count" AS tags_xml, coalesce(c.n, 0) AS computed
        FROM tags t LEFT JOIN computed c ON t.TagName = c.tag
        WHERE t.site = 'stackoverflow.com' ORDER BY t."Count" DESC LIMIT 300
        """
    ).df()
    df["pct_diff"] = 100 * (df["computed"] - df["tags_xml"]) / df["tags_xml"]
    return {
        "n_tags_compared": int(len(df)),
        "median_pct_diff": round(float(df["pct_diff"].median()), 3),
        "max_abs_pct_diff": round(float(df["pct_diff"].abs().max()), 3),
        "worst": df.reindex(df["pct_diff"].abs().sort_values(ascending=False).index)
        .head(5)
        .round(3)
        .to_dict("records"),
    }


def weekly_counts(con) -> pd.DataFrame:
    return con.execute(
        "SELECT site, date_trunc('week', CreationDate)::DATE AS week, count(*) AS questions "
        "FROM q GROUP BY 1, 2 ORDER BY 1, 2"
    ).df()


def _kind(week: pd.Timestamp, launch: pd.Timestamp) -> str:
    if week < launch:
        return "pre_launch"
    if (week.month == 12 and week.day >= 16) or (week.month == 1 and week.day <= 7):
        return "holiday"
    return "other"


def find_anomalies(weekly: pd.DataFrame) -> pd.DataFrame:
    """Weeks whose log count is > ANOMALY_Z robust z-scores from a centred 13-week median,
    plus weeks with zero questions. Each is labelled pre_launch (before the site's first
    4 consecutive weeks with >= 10 questions; migrated old questions), holiday, or other."""
    out = []
    for site, g in weekly.groupby("site"):
        g = g.set_index("week")["questions"]
        g.index = pd.to_datetime(g.index)
        g = g.asfreq("W-MON", fill_value=0)
        g = g.iloc[1:-1]  # first and last weeks are partial
        active = (g >= 10).rolling(4).sum() == 4
        launch = (
            pd.Timestamp(active.idxmax()) - pd.Timedelta(weeks=3) if active.any() else g.index[-1]
        )
        logc = np.log1p(g)
        med = logc.rolling(ROLLING_WEEKS, center=True, min_periods=7).median()
        resid = logc - med
        mad = resid.abs().rolling(52, center=True, min_periods=26).median() * 1.4826
        z = resid / mad.replace(0, np.nan)
        flag = (z.abs() > ANOMALY_Z) | (g == 0)
        for week in g.index[flag.fillna(False)]:
            out.append(
                {
                    "site": site,
                    "week": week.date().isoformat(),
                    "kind": _kind(week, launch),
                    "questions": int(g[week]),
                    "rolling_median": round(float(np.expm1(med[week])), 1),
                    "robust_z": round(float(z[week]), 1) if pd.notna(z[week]) else None,
                }
            )
    return pd.DataFrame(out)


def plot_weekly(weekly: pd.DataFrame, anomalies: pd.DataFrame, path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    surface, ink, ink2, grid, series = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#2a78d6"
    ev = events.load_events()
    marks = ev[ev["role"].isin(["primary_break", "exclusion_window"])]

    fig, axes = plt.subplots(len(CHART_SITES), 1, figsize=(11, 10), sharex=True)
    fig.patch.set_facecolor(surface)
    for ax, site in zip(axes, CHART_SITES, strict=True):
        g = weekly[weekly["site"] == site].iloc[1:-1]
        g = g[pd.to_datetime(g["week"]) >= pd.Timestamp("2010-01-01")]
        ax.set_facecolor(surface)
        for r in marks.itertuples():
            if pd.notna(r.end_date):
                ax.axvspan(r.date, r.end_date, color=grid, alpha=0.6, lw=0)
            else:
                ax.axvline(r.date, color=ink2, lw=1, ls=(0, (3, 3)))
        ax.plot(g["week"], g["questions"], color=series, lw=1.2)
        a = anomalies[(anomalies["site"] == site) & (anomalies["kind"] == "other")]
        if len(a):
            wk = pd.to_datetime(a["week"])
            ax.scatter(wk, a["questions"].clip(lower=1), s=18, color=ink, zorder=3)
        ax.set_yscale("log")
        ax.set_xlim(
            pd.Timestamp("2010-01-01"), pd.Timestamp(g["week"].max()) + pd.Timedelta(weeks=8)
        )
        ax.set_title(site, loc="left", fontsize=10, color=ink)
        ax.grid(axis="y", color=grid, lw=0.6)
        ax.tick_params(colors=ink2, labelsize=8)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_ylabel("questions / week", fontsize=8, color=ink2)
    chatgpt = marks[marks["role"] == "primary_break"]["date"].iloc[0]
    axes[0].annotate(
        "ChatGPT",
        (chatgpt, 1),
        xycoords=("data", "axes fraction"),
        xytext=(4, -10),
        textcoords="offset points",
        fontsize=8,
        color=ink2,
    )
    axes[-1].xaxis.set_major_locator(mdates.YearLocator(2))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.suptitle(
        "Weekly new questions (log scale). Shaded: COVID window and moderator strike. "
        "Dots: unusual weeks (holidays and pre-launch weeks not shown).",
        x=0.01,
        ha="left",
        fontsize=10,
        color=ink2,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, facecolor=surface)
    plt.close(fig)


def main() -> None:
    import sys

    t0 = time.monotonic()
    con = connect()
    if "--weekly-only" in sys.argv:  # re-run anomalies and chart without the slow checks
        con.execute(
            "CREATE TEMP TABLE q AS SELECT site, CreationDate FROM posts WHERE PostTypeId = 1"
        )
        weekly = weekly_counts(con)
        anomalies = find_anomalies(weekly)
        anomalies.to_csv(QA_DIR / "weekly_anomalies.csv", index=False)
        plot_weekly(weekly, anomalies, config.FIGURE_DIR / "qa_weekly_questions.png")
        result = json.loads((QA_DIR / "quality.json").read_text())
        result["n_anomalies"] = int(len(anomalies))
        result["anomalies_by_kind"] = anomalies["kind"].value_counts().to_dict()
        (QA_DIR / "quality.json").write_text(json.dumps(result, indent=2, default=str))
        print(result["anomalies_by_kind"])
        return
    checks = run_checks(con)
    tags = tag_count_comparison(con)
    weekly = weekly_counts(con)
    anomalies = find_anomalies(weekly)
    QA_DIR.mkdir(parents=True, exist_ok=True)
    anomalies.to_csv(QA_DIR / "weekly_anomalies.csv", index=False)
    plot_weekly(weekly, anomalies, config.FIGURE_DIR / "qa_weekly_questions.png")
    result = {
        "generated_seconds": round(time.monotonic() - t0, 1),
        "checks": checks,
        "totals": {k: sum(v.values()) for k, v in checks.items()},
        "tags_xml_vs_computed": tags,
        "n_anomalies": int(len(anomalies)),
        "anomalies_by_kind": anomalies["kind"].value_counts().to_dict(),
    }
    (QA_DIR / "quality.json").write_text(json.dumps(result, indent=2, default=str))
    print(
        json.dumps(
            {
                "totals": result["totals"],
                "tags": tags,
                "n_anomalies": len(anomalies),
                "seconds": result["generated_seconds"],
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
