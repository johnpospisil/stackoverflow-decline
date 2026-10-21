"""P25: where did help-seeking go? GitHub issue activity vs Stack Overflow tags (exploratory E2).

GH Archive (BigQuery `githubarchive.month.*`), monthly 2019-01..2026-09: counts of IssuesEvent
(issues opened, closed or reopened) and IssueCommentEvent for the flagship repository of each
technology, matched by repository id (rename-safe), plus all other repositories as a baseline.
The opened/closed split needs the `payload` column (~470 GB per month), so total issue activity
is used. GitHub Discussions are not in GH Archive, and it has no repository-language field.

The query scans ~196 GB (free BigQuery sandbox: 1 TB a month); it is capped at 250 GB and its
result is cached in data/reference/gharchive_issue_activity_monthly.csv, so it runs once.

Comparison per technology: index (2019-2021 mean = 100) of monthly SO questions in the tag vs
GitHub issue activity in the flagship repo; levels are monthly medians over 2023, 2024 and
2025-01..05. Later months are not used: GH Archive coverage degrades from mid-2025 (comment
events fall everywhere) and nearly vanishes in 2026-05..08; Oct-Nov 2024 has a platform-wide
burst of issue events (bots/spam), which monthly medians absorb.

Usage: python -m sod.models.github [--refresh]
"""

from __future__ import annotations

import io
import json
import subprocess
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from sod import config  # noqa: E402

CACHE = config.REFERENCE_DIR / "gharchive_issue_activity_monthly.csv"
MAX_BYTES = 250_000_000_000
QA = config.REPO_ROOT / "report" / "qa"
TABLES = config.REPO_ROOT / "report" / "tables"

# repo id: (full name, Stack Overflow tag or None)
REPOS = {
    858127: ("pandas-dev/pandas", "pandas"),
    908607: ("numpy/numpy", "numpy"),
    10270250: ("facebook/react", "reactjs"),
    70107786: ("vercel/next.js", "next.js"),
    31792824: ("flutter/flutter", "flutter"),
    20929025: ("microsoft/TypeScript", "typescript"),
    27193779: ("nodejs/node", "node.js"),
    724712: ("rust-lang/rust", "rust"),
    23096959: ("golang/go", "go"),
    137078487: ("vuejs/core", "vue.js"),
    24195339: ("angular/angular", "angular"),
    65600975: ("pytorch/pytorch", "pytorch"),
    45717250: ("tensorflow/tensorflow", "tensorflow"),
    7691631: ("moby/moby", "docker"),
    20580498: ("kubernetes/kubernetes", "kubernetes"),
    6296790: ("spring-projects/spring-boot", "spring-boot"),
    35726310: ("dart-lang/sdk", "dart"),
    44838949: ("swiftlang/swift", None),  # issues moved to GitHub in 2022 (bugs.swift.org)
    210716005: ("dotnet/runtime", ".net-core"),
    1385122: ("matplotlib/matplotlib", "matplotlib"),
    843222: ("scikit-learn/scikit-learn", "scikit-learn"),
    # descriptive only: no matching top-300 tag or no comparable pre-period on GitHub
    81598961: ("python/cpython", None),  # issues moved to GitHub in 2022-04
    41881900: ("microsoft/vscode", None),
    106017343: ("tailwindlabs/tailwindcss", None),
    257485422: ("vitejs/vite", None),
}

SQL = """
SELECT _TABLE_SUFFIX AS month, type,
       IF(repo.id IN ({ids}), repo.id, 0) AS repo_id,
       COUNT(*) AS events
FROM `githubarchive.month.*`
WHERE _TABLE_SUFFIX BETWEEN '201901' AND '202609'
  AND type IN ('IssuesEvent', 'IssueCommentEvent')
GROUP BY 1, 2, 3
"""


def query(refresh: bool = False) -> pd.DataFrame:
    if CACHE.exists() and not refresh:
        return pd.read_csv(CACHE, dtype={"month": str})
    sql = SQL.format(ids=", ".join(str(i) for i in REPOS))
    out = subprocess.run(
        [
            "bq",
            "query",
            "--use_legacy_sql=false",
            "--format=csv",
            "--max_rows=1000000",
            f"--maximum_bytes_billed={MAX_BYTES}",
            sql,
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    df = pd.read_csv(io.StringIO(out[out.index("month,") :]), dtype={"month": str})
    df.sort_values(["month", "type", "repo_id"]).to_csv(CACHE, index=False)
    return df


def monthly(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["period"] = pd.to_datetime(df["month"], format="%Y%m")
    w = df.pivot_table(
        index=["period", "repo_id"], columns="type", values="events", aggfunc="sum", fill_value=0
    ).reset_index()
    w["repo"] = w["repo_id"].map(lambda i: REPOS.get(i, ("all other repositories", None))[0])
    w["tag"] = w["repo_id"].map(lambda i: REPOS.get(i, (None, None))[1])
    return w


WINDOWS = {
    "2023": ("2023-01-01", "2023-12-01"),
    "2024": ("2024-01-01", "2024-12-01"),
    "2025h1": ("2025-01-01", "2025-05-01"),
}


def lvl(s: pd.Series, start: str, end: str) -> float:
    return float(s.loc[start:end].median())


def index_100(s: pd.Series, active_only: bool = False) -> pd.Series:
    """Index with the 2019-2021 mean = 100. With active_only, the base skips a repository's
    start-up months (before it first reaches half its 2021 median), e.g. vuejs/core (2020)
    and dotnet/runtime (2019-11), so near-empty early months don't deflate the base."""
    win = s[(s.index >= "2019-01-01") & (s.index < "2022-01-01")]
    if active_only:
        start = win[win >= 0.5 * s[s.index.year == 2021].median()].index.min()
        win = win[win.index >= start]
    out = 100 * s / win.mean()
    return out.where(out > 0)  # zero months as gaps on log scales


def compare(gh: pd.DataFrame) -> pd.DataFrame:
    tm = pd.read_parquet(config.PANEL_DIR / "tag_month.parquet")
    tm = tm[~tm["partial_period"]]
    rows = []
    for rid, (name, tag) in REPOS.items():
        if tag is None:
            continue
        g = gh[gh["repo_id"] == rid].set_index("period")["IssuesEvent"].sort_index()
        q = tm[tm["tag"] == tag].set_index("period")["questions"].sort_index()
        gi, qi = index_100(g, active_only=True), index_100(q.loc["2019-01-01":])

        rows.append(
            {
                "tag": tag,
                "repo": name,
                **{f"so_{k}": lvl(qi, *v) for k, v in WINDOWS.items()},
                **{f"gh_{k}": lvl(gi, *v) for k, v in WINDOWS.items()},
                "gh_issue_events_2019_21_per_month": float(
                    g[(g.index >= "2019-01-01") & (g.index < "2022-01-01")].mean()
                ),
            }
        )
    out = pd.DataFrame(rows)
    for k in WINDOWS:
        out[f"log_gap_{k}"] = np.log(out[f"gh_{k}"] / out[f"so_{k}"])
    return out.sort_values("gh_2025h1").reset_index(drop=True)


def fig_compare(gh: pd.DataFrame, path) -> None:
    tm = pd.read_parquet(config.PANEL_DIR / "tag_month.parquet")
    tm = tm[~tm["partial_period"]]
    pairs = [(rid, n, t) for rid, (n, t) in REPOS.items() if t]
    cols = 7
    rows = int(np.ceil((len(pairs) + 1) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(18, 2.6 * rows), sharey=True)
    base = gh[gh["repo_id"] == 0].set_index("period")["IssuesEvent"].sort_index()
    for ax, (rid, name, tag) in zip(axes.flat, pairs, strict=False):
        g = index_100(
            gh[gh["repo_id"] == rid].set_index("period")["IssuesEvent"].sort_index(),
            active_only=True,
        )
        q = index_100(
            tm[tm["tag"] == tag].set_index("period")["questions"].sort_index().loc["2019-01-01":]
        )
        g = g.loc[:"2025-05-01"]  # GH Archive coverage degrades afterwards
        ax.plot(g.index, g.rolling(3, min_periods=1).median(), color="#0072B2", lw=1.5)
        ax.plot(q.index, q, color="#D55E00", lw=1.5)
        ax.set_title(f"{tag}\n{name}", fontsize=7, loc="left")
        ax.axvline(pd.Timestamp(config.BREAK_DATE), color="#333333", lw=0.8, ls=":")
        ax.set_yscale("log")
        ax.tick_params(labelsize=6)
        ax.spines[["top", "right"]].set_visible(False)
    ax = axes.flat[len(pairs)]
    ax.plot(
        base.loc[:"2025-05-01"].index, index_100(base).loc[:"2025-05-01"], color="#999999", lw=1.5
    )
    ax.set_title("all other GitHub repos\n(issue events)", fontsize=7, loc="left")
    ax.set_yscale("log")
    ax.tick_params(labelsize=6)
    for ax in list(axes.flat)[len(pairs) + 1 :]:
        ax.axis("off")
    axes.flat[0].set_yticks([1, 10, 100, 300], ["1", "10", "100", "300"])
    fig.suptitle(
        "Index, 2019–21 = 100 (log): Stack Overflow questions in the tag (orange) vs "
        "issue events in the flagship GitHub repository (blue, 3-month median, to 2025-05)",
        x=0.01,
        ha="left",
        fontsize=11,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def run(refresh: bool = False) -> dict:
    gh = monthly(query(refresh))
    cmp = compare(gh)
    base = gh[gh["repo_id"] == 0].set_index("period")
    base_idx = index_100(base["IssuesEvent"])
    summary = {
        "months": [str(gh["period"].min().date()), str(gh["period"].max().date())],
        "pairs": len(cmp),
        "median_so_index": {k: float(cmp[f"so_{k}"].median()) for k in WINDOWS},
        "median_gh_index": {k: float(cmp[f"gh_{k}"].median()) for k in WINDOWS},
        "pairs_gh_above_so_2025h1": int((cmp["gh_2025h1"] > cmp["so_2025h1"]).sum()),
        "corr_so_gh_2025h1_log": float(
            np.corrcoef(np.log(cmp["so_2025h1"]), np.log(cmp["gh_2025h1"]))[0, 1]
        ),
        "all_github_issue_events_index_median": {k: lvl(base_idx, *v) for k, v in WINDOWS.items()},
        "comparison": cmp.round(2).to_dict(orient="records"),
    }
    survey = pd.read_csv(config.REFERENCE_DIR / "so_survey_ai_use.csv")
    summary["so_survey_ai_use"] = survey.where(survey.notna(), None).to_dict(orient="records")
    cmp.round(3).to_csv(TABLES / "github_vs_stackoverflow.csv", index=False)
    (QA / "github_summary.json").write_text(json.dumps(summary, indent=2))
    fig_compare(gh, config.FIGURE_DIR / "github_vs_stackoverflow.png")
    return summary


if __name__ == "__main__":
    print(json.dumps(run(refresh="--refresh" in sys.argv), indent=2))
