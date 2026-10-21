"""P12: user activity, posting cohorts and answer concentration, all sites.

Outputs under <PARQUET_DIR>/<table>/site=<site>/data.parquet:
  user_months           one row per user x month with any activity: questions, answers, comments
  user_summary          one row per user who ever asked or answered: first/second post,
                        totals, 2019-2021 answers, core_answerer (top 1% of 2019-2021 answerers)
  cohort_activity       first-post cohort (month) x months since first post: cohort size and
                        how many posted (question or answer) in that month
  answer_concentration  per year: answerers, answers, Gini of answers per answerer, share of
                        answers from the top 1% of that year's answerers, active core answerers

"New user" means a user's first question or answer, not account creation (most accounts
never post). Deleted users (no OwnerUserId) and the Community user (-1) are excluded.

Usage: python -m sod.build.cohorts [site ...]
"""

from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path

from sod import config, progress
from sod.db import connect

JOB = "cohorts"
CORE_SHARE = 0.01
OUTPUTS = ("user_months", "user_summary", "cohort_activity", "answer_concentration")

SQL = {
    "prep": """
        CREATE OR REPLACE TEMP TABLE p AS
        SELECT OwnerUserId AS user_id, PostTypeId, CreationDate FROM posts
        WHERE site = '{site}' AND PostTypeId IN (1, 2) AND OwnerUserId > 0;
        CREATE OR REPLACE TEMP TABLE c AS
        SELECT UserId AS user_id, CreationDate FROM comments
        WHERE site = '{site}' AND UserId > 0;
    """,
    "user_months": """
        SELECT '{site}' AS site, user_id, month,
               sum(nq)::INTEGER AS n_questions, sum(na)::INTEGER AS n_answers,
               sum(nc)::INTEGER AS n_comments
        FROM (
            SELECT user_id, date_trunc('month', CreationDate)::DATE AS month,
                   (PostTypeId = 1)::INT AS nq, (PostTypeId = 2)::INT AS na, 0 AS nc FROM p
            UNION ALL
            SELECT user_id, date_trunc('month', CreationDate)::DATE, 0, 0, 1 FROM c
        ) GROUP BY ALL
    """,
    "user_summary": """
        WITH ranked AS (
            SELECT user_id, PostTypeId, CreationDate,
                   row_number() OVER (PARTITION BY user_id ORDER BY CreationDate, PostTypeId) AS k
            FROM p
        ),
        per_user AS (
            SELECT user_id,
                   min(CreationDate) AS first_post_at,
                   any_value(CASE WHEN k = 1 THEN PostTypeId END) AS first_type,
                   min(CASE WHEN k = 2 THEN CreationDate END) AS second_post_at,
                   max(CreationDate) AS last_post_at,
                   count(*) FILTER (WHERE PostTypeId = 1) AS n_questions,
                   count(*) FILTER (WHERE PostTypeId = 2) AS n_answers,
                   count(*) FILTER (WHERE PostTypeId = 2 AND CreationDate >= '2019-01-01'
                                    AND CreationDate < '2022-01-01') AS answers_2019_2021
            FROM ranked GROUP BY 1
        ),
        core AS (
            SELECT user_id FROM (
                SELECT user_id, row_number() OVER (ORDER BY answers_2019_2021 DESC, user_id) AS r,
                       count(*) OVER () AS n
                FROM per_user WHERE answers_2019_2021 > 0
            ) WHERE r <= ceil({core_share} * n)
        )
        SELECT '{site}' AS site, u.user_id,
               date_trunc('month', first_post_at)::DATE AS first_post_month,
               first_post_at,
               CASE first_type WHEN 1 THEN 'question' ELSE 'answer' END AS first_post_type,
               date_diff('millisecond', first_post_at, second_post_at) / 86400000.0
                   AS days_to_second_post,
               last_post_at, n_questions::INTEGER AS n_questions, n_answers::INTEGER AS n_answers,
               answers_2019_2021::INTEGER AS answers_2019_2021,
               core.user_id IS NOT NULL AS core_answerer
        FROM per_user u LEFT JOIN core USING (user_id)
    """,
    "cohort_activity": """
        WITH first AS (
            SELECT user_id, date_trunc('month', min(CreationDate))::DATE AS cohort_month
            FROM p GROUP BY 1
        ),
        sizes AS (SELECT cohort_month, count(*) AS cohort_size FROM first GROUP BY 1),
        act AS (
            SELECT DISTINCT p.user_id, f.cohort_month,
                   date_diff('month', f.cohort_month, date_trunc('month', p.CreationDate)::DATE)
                       AS months_since
            FROM p JOIN first f USING (user_id)
        )
        SELECT '{site}' AS site, a.cohort_month, a.months_since::INTEGER AS months_since,
               s.cohort_size::INTEGER AS cohort_size, count(*)::INTEGER AS active
        FROM act a JOIN sizes s USING (cohort_month) GROUP BY ALL
    """,
    "answer_concentration": """
        WITH per AS (
            SELECT year(CreationDate) AS year, user_id, count(*) AS n FROM p
            WHERE PostTypeId = 2 GROUP BY 1, 2
        ),
        r AS (
            SELECT *, row_number() OVER (PARTITION BY year ORDER BY n) AS i_asc,
                   row_number() OVER (PARTITION BY year ORDER BY n DESC) AS i_desc,
                   count(*) OVER (PARTITION BY year) AS m, sum(n) OVER (PARTITION BY year) AS tot
            FROM per
        ),
        core AS (SELECT user_id FROM user_summary_tmp WHERE core_answerer)
        SELECT '{site}' AS site, year::INTEGER AS year, any_value(m)::INTEGER AS answerers,
               any_value(tot)::BIGINT AS answers,
               2.0 * sum(i_asc * n) / (any_value(m) * any_value(tot))
                   - (any_value(m) + 1.0) / any_value(m) AS gini,
               sum(n) FILTER (WHERE i_desc <= ceil({core_share} * m)) / any_value(tot)
                   AS top1pct_share,
               count(*) FILTER (WHERE user_id IN (SELECT user_id FROM core))::INTEGER
                   AS core_answerers_active,
               coalesce(sum(n) FILTER (WHERE user_id IN (SELECT user_id FROM core)), 0)
                   / any_value(tot) AS core_answer_share
        FROM r GROUP BY year
    """,
}


def build_site(site: str, out_root: Path, job: str = JOB) -> dict[str, int]:
    con = connect()
    reporter = progress.Reporter(job, site, len(OUTPUTS) + 1)
    counts: dict[str, int] = {}
    try:
        con.execute(SQL["prep"].format(site=site))
        reporter.update(1, 0)
        for i, name in enumerate(OUTPUTS, start=2):
            sql = SQL[name].format(site=site, core_share=CORE_SHARE)
            out_dir = out_root / name / f"site={site}"
            if out_dir.exists():
                shutil.rmtree(out_dir)
            out_dir.mkdir(parents=True)
            target = out_dir / "data.parquet"
            con.execute(f"COPY ({sql}) TO '{target}' (FORMAT parquet, COMPRESSION zstd)")
            if name == "user_summary":
                con.execute(f"CREATE OR REPLACE TEMP TABLE user_summary_tmp AS FROM '{target}'")
            counts[name] = con.execute(f"SELECT count(*) FROM '{target}'").fetchone()[0]
            reporter._last = 0
            reporter.update(i, counts[name])
    except BaseException:
        reporter.finish(0, status="failed")
        raise
    reporter.finish(counts["user_summary"])
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sites", nargs="*")
    args = ap.parse_args()
    con = connect()
    n_posts = dict(con.execute("SELECT site, count(*) FROM posts GROUP BY 1").fetchall())
    sites = sorted(args.sites or config.ALL_SITES, key=lambda s: n_posts.get(s, 0), reverse=True)
    # Progress weights: each site's share of all posts (Stack Overflow dominates).
    progress.write_manifest(JOB, {s: n_posts.get(s, 1) for s in sites})
    for site in sites:
        t0 = time.monotonic()
        counts = build_site(site, config.PARQUET_DIR, job=JOB)
        print(f"done  {site:<40} {counts}  {time.monotonic() - t0:5.0f}s", flush=True)


if __name__ == "__main__":
    main()
