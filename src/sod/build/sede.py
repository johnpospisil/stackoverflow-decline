"""P09: reconcile dump monthly counts with SEDE, and measure deleted posts.

Inputs (saved by hand from data.stackexchange.com, see data/reference/sede/queries/):
  data/reference/sede/so_monthly.csv           Stack Overflow, questions + answers
  data/reference/sede/other_sites_monthly.csv  all other non-meta sites, questions
Outputs: report/qa/sede_reconciliation.csv, report/qa/sede_summary.json,
         report/figures/qa_deleted_share.png

Usage: python -m sod.build.sede
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from sod import config
from sod.db import connect

SEDE_DIR = config.REFERENCE_DIR / "sede"
QA_DIR = config.REPORT_DIR / "qa"

DB_TO_SITE = {
    "StackOverflow": "stackoverflow.com",
    "ServerFault": "serverfault.com",
    "SuperUser": "superuser.com",
    "StackExchange.Ubuntu": "askubuntu.com",
    "StackExchange.Programmers": "softwareengineering.stackexchange.com",
    "StackOverflow.Br": "pt.stackoverflow.com",
    "StackOverflow.Es": "es.stackoverflow.com",
    "StackOverflow.Ja": "ja.stackoverflow.com",
    "StackOverflow.Ru": "ru.stackoverflow.com",
}


def db_to_site(db: str) -> str | None:
    """Map a SEDE database name to our site name; None if not one of our sites."""
    site = DB_TO_SITE.get(db)
    if site is None and db.startswith("StackExchange."):
        site = db.split(".", 1)[1].lower() + ".stackexchange.com"
    return site if site in config.ALL_SITES else None


def load_sede() -> pd.DataFrame:
    so = pd.read_csv(SEDE_DIR / "so_monthly.csv", parse_dates=["month", "sede_snapshot"])
    so = so[so["PostTypeId"] == 1].assign(site=config.TREATED)
    other = pd.read_csv(SEDE_DIR / "other_sites_monthly.csv", parse_dates=["month"])
    other["site"] = other["db"].map(db_to_site)
    other = other.dropna(subset=["site"])
    cols = ["site", "month", "total", "not_deleted", "deleted"]
    return pd.concat([so[cols], other[cols]], ignore_index=True)


def dump_monthly(con) -> pd.DataFrame:
    df = con.execute(
        "SELECT site, date_trunc('month', CreationDate) AS month, count(*) AS dump "
        "FROM posts WHERE PostTypeId = 1 AND CreationDate >= '2017-01-01' "
        "AND CreationDate < '2026-10-01' GROUP BY 1, 2"
    ).df()
    df["month"] = pd.to_datetime(df["month"])
    return df


def votes_deleted_so(con) -> pd.DataFrame:
    """Deleted Stack Overflow posts visible through Votes, by month of first vote
    (lower bound: posts deleted without any vote are invisible; questions and answers mixed)."""
    df = con.execute(
        """
        WITH o AS (
            SELECT v.PostId, min(v.CreationDate) AS first_vote FROM votes v
            ANTI JOIN (SELECT Id FROM posts WHERE site = 'stackoverflow.com') p ON v.PostId = p.Id
            WHERE v.site = 'stackoverflow.com' GROUP BY 1
        )
        SELECT date_trunc('month', first_vote) AS month, count(*) AS deleted_via_votes
        FROM o WHERE first_vote >= '2017-01-01' GROUP BY 1
        """
    ).df()
    df["month"] = pd.to_datetime(df["month"])
    return df


def summarize(rec: pd.DataFrame) -> dict:
    out = {}
    for site, g in rec.groupby("site"):
        pre = g[(g["month"] >= "2017-01-01") & (g["month"] < "2022-12-01")]
        post = g[g["month"] >= "2022-12-01"]
        late = g[g["month"] >= "2025-10-01"]
        # change Sep-Nov 2022 -> Jul-Sep 2026 under each count definition
        a = g[(g["month"] >= "2022-09-01") & (g["month"] < "2022-12-01")]
        b = g[(g["month"] >= "2026-07-01") & (g["month"] < "2026-10-01")]

        def share(x: pd.DataFrame) -> float | None:
            return float(x["deleted"].sum() / x["total"].sum()) if x["total"].sum() else None

        def log_change(col: str, a: pd.DataFrame, b: pd.DataFrame) -> float | None:
            before, after = a[col].sum(), b[col].sum()
            return round(float(np.log(after / before)), 3) if before and after else None

        out[site] = {
            "group": config.site_group(site),
            "deleted_share_pre": share(pre) and round(share(pre), 4),
            "deleted_share_post": share(post) and round(share(post), 4),
            "deleted_share_last12": share(late) and round(share(late), 4),
            "dump_vs_sede_not_deleted_max_abs_pct": round(float(g["diff_pct"].abs().max()), 3),
            "log_change_dump": log_change("dump", a, b),
            "log_change_incl_deleted": log_change("total", a, b),
        }
    return out


def plot_deleted_share(rec: pd.DataFrame, path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    surface, ink, ink2, grid = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
    series = {"treated": "#2a78d6", "donor median": "#eb6834", "tech median": "#1baf7a"}
    rec = rec.assign(share=rec["deleted"] / rec["total"])
    so = rec[rec["site"] == config.TREATED].set_index("month")["share"]
    med = {
        "donor median": rec[rec["group"] == "donor"].groupby("month")["share"].median(),
        "tech median": rec[rec["group"] == "tech_exposed"].groupby("month")["share"].median(),
    }
    fig, ax = plt.subplots(figsize=(10, 4.5))
    fig.patch.set_facecolor(surface)
    ax.set_facecolor(surface)
    ax.axvline(pd.Timestamp(config.BREAK_DATE), color=ink2, lw=1, ls=(0, (3, 3)))
    lines = {"Stack Overflow": (so, series["treated"])}
    lines["tech sites (median)"] = (med["tech median"], series["tech median"])
    lines["comparison sites (median)"] = (med["donor median"], series["donor median"])
    labels = []
    for name, (s, color) in lines.items():
        ax.plot(s.index, 100 * s, color=color, lw=2)
        labels.append([100 * s.iloc[-1], name, s.index[-1]])
    labels.sort(key=lambda t: t[0])
    for i in range(1, len(labels)):  # keep end labels at least 4 points apart
        labels[i][0] = max(labels[i][0], labels[i - 1][0] + 4)
    for y, name, x in labels:
        ax.text(x, y, "  " + name, color=ink, fontsize=9, va="center")
    ax.set_ylabel("% of questions since deleted", color=ink2, fontsize=9)
    ax.set_ylim(0, None)
    ax.grid(axis="y", color=grid, lw=0.6)
    ax.tick_params(colors=ink2, labelsize=8)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title(
        "Share of each month's questions deleted by mid-Oct 2026 (SEDE). Dashed: ChatGPT.",
        loc="left",
        fontsize=10,
        color=ink2,
    )
    ax.set_xlim(right=pd.Timestamp(so.index[-1]) + pd.Timedelta(days=420))
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=surface)
    plt.close(fig)


def main() -> None:
    con = connect()
    sede = load_sede()
    dump = dump_monthly(con)
    rec = sede.merge(dump, on=["site", "month"], how="outer").fillna(0)
    rec["group"] = rec["site"].map(config.site_group)
    base = rec["not_deleted"].replace(0, np.nan)
    rec["diff_pct"] = 100 * (rec["dump"] - rec["not_deleted"]) / base
    rec = rec.sort_values(["site", "month"])
    QA_DIR.mkdir(parents=True, exist_ok=True)
    rec.to_csv(QA_DIR / "sede_reconciliation.csv", index=False)

    votes = votes_deleted_so(con)
    so_all = pd.read_csv(SEDE_DIR / "so_monthly.csv")  # questions + answers
    so_deleted_qa = int(so_all["deleted"].sum())
    summary = {
        "sites_matched": int(rec["site"].nunique()),
        "sites_missing": sorted(
            set(config.ALL_SITES) - set(rec["site"]) - {"meta.stackoverflow.com"}
        ),
        "by_site": summarize(rec),
        # Both cover questions + answers first seen 2017-01 to 2026-09 (votes: by first vote).
        "so_deleted_qa_sede": so_deleted_qa,
        "so_deleted_posts_via_votes": int(votes["deleted_via_votes"].sum()),
        "so_votes_coverage_of_sede_deleted": round(
            float(votes["deleted_via_votes"].sum() / so_deleted_qa), 3
        ),
    }
    (QA_DIR / "sede_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    plot_deleted_share(rec, config.FIGURE_DIR / "qa_deleted_share.png")
    print(json.dumps({k: v for k, v in summary.items() if k != "by_site"}, indent=2))
    print(pd.DataFrame(summary["by_site"]).T.sort_values("log_change_dump").to_string())


if __name__ == "__main__":
    main()
