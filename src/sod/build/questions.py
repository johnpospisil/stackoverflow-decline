"""P10: one analysis row per question (questions.parquet), all sites.

Output: <PARQUET_DIR>/questions/site=<site>/part-<year>.parquet
Progress: job "questions" (make progress). Stack Overflow is built one year at a time.

Fields
- tags: tags at time of asking (PostHistory type 3), falling back to current tags
  (prereg clarification 2026-10-20); tags_source says which.
- hours_to_first_answer: first answer still in the dump; answers dated before the
  question (merged duplicates) are ignored.
- ever_closed / first_close_reason / closed_as_duplicate: from PostHistory close events
  of posts still in the dump.
- asker_account_age_days, asker_first_post: NULL when the asker's account is deleted.
  asker_first_post means no earlier question or answer by that user on the site.
- Score, ViewCount, n_answers, CommentCount are as of the dump date, so older questions
  have had longer to accumulate them.

Usage: python -m sod.build.questions [site ...]
"""

from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path

from sod import config, progress
from sod.db import connect

JOB = "questions"
PREP_SHARE = 0.3  # share of a site's progress bar given to the per-site preparation


def _prepare(con, site: str) -> None:
    """Per-site lookup tables, reused by every year's chunk."""
    s = f"'{site}'"
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE q AS
        SELECT * EXCLUDE (site) FROM posts WHERE site = {s} AND PostTypeId = 1;
        CREATE OR REPLACE TEMP TABLE ans AS
        SELECT a.ParentId, min(a.CreationDate) AS first_answer_at, count(*) AS n_answers
        FROM posts a JOIN q ON a.ParentId = q.Id
        WHERE a.site = {s} AND a.PostTypeId = 2 AND a.CreationDate >= q.CreationDate
        GROUP BY 1;
        CREATE OR REPLACE TEMP TABLE first_post AS
        SELECT OwnerUserId, min(CreationDate) AS first_post_at FROM posts
        WHERE site = {s} AND PostTypeId IN (1, 2) AND OwnerUserId IS NOT NULL GROUP BY 1;
        CREATE OR REPLACE TEMP TABLE init_tags AS
        SELECT PostId, arg_min(tags, Id) AS tags FROM posthistory
        WHERE site = {s} AND PostHistoryTypeId = 3 GROUP BY 1;
        CREATE OR REPLACE TEMP TABLE closes AS
        SELECT PostId, min(CreationDate) AS first_close_at,
               arg_min(close_reason_id, CreationDate) AS first_close_reason,
               bool_or(is_duplicate) AS closed_as_duplicate
        FROM posthistory WHERE site = {s} AND PostHistoryTypeId = 10 GROUP BY 1;
        CREATE OR REPLACE TEMP TABLE u AS
        SELECT Id, CreationDate AS user_created FROM users WHERE site = {s};
        """
    )


SELECT_SQL = """
SELECT
    '{site}' AS site,
    q.Id,
    q.CreationDate,
    date_trunc('week', q.CreationDate)::DATE AS week,
    date_trunc('month', q.CreationDate)::DATE AS month,
    coalesce(it.tags, q.tags) AS tags,
    CASE WHEN it.tags IS NULL THEN 'current' ELSE 'initial' END AS tags_source,
    len(coalesce(it.tags, q.tags))::TINYINT AS n_tags,
    q.tags AS tags_current,
    q.body_chars, q.text_chars, q.code_chars, q.n_code_blocks, q.n_inline_code,
    q.n_links, q.n_images, q.title_chars, q.title_words,
    q.n_code_blocks > 0 AS has_code,
    q.Score, q.ViewCount, q.CommentCount,
    coalesce(a.n_answers, 0)::INTEGER AS n_answers,
    q.AcceptedAnswerId IS NOT NULL AS has_accepted_answer,
    a.first_answer_at,
    date_diff('millisecond', q.CreationDate, a.first_answer_at) / 3600000.0
        AS hours_to_first_answer,
    c.first_close_at IS NOT NULL AS ever_closed,
    c.first_close_at,
    c.first_close_reason,
    coalesce(c.closed_as_duplicate, false) AS closed_as_duplicate,
    q.ClosedDate IS NOT NULL AS currently_closed,
    q.OwnerUserId,
    q.owner_deleted,
    CASE WHEN usr.user_created IS NULL THEN NULL
         ELSE date_diff('millisecond', usr.user_created, q.CreationDate) / 86400000.0
    END AS asker_account_age_days,
    CASE WHEN fp.first_post_at IS NULL THEN NULL
         ELSE fp.first_post_at >= q.CreationDate
    END AS asker_first_post
FROM q
LEFT JOIN ans a ON a.ParentId = q.Id
LEFT JOIN init_tags it ON it.PostId = q.Id
LEFT JOIN closes c ON c.PostId = q.Id
LEFT JOIN u usr ON usr.Id = q.OwnerUserId
LEFT JOIN first_post fp ON fp.OwnerUserId = q.OwnerUserId
WHERE {where}
"""


def build_site(site: str, out_root: Path, job: str = JOB, by_year: bool = False) -> int:
    con = connect()
    n_total = con.execute(
        f"SELECT count(*) FROM posts WHERE site = '{site}' AND PostTypeId = 1"
    ).fetchone()[0]
    reporter = progress.Reporter(job, site, max(n_total, 1))
    out_dir = out_root / f"site={site}"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    try:
        _prepare(con, site)
        prep_units = int(PREP_SHARE * n_total)
        reporter.update(prep_units, 0)
        if by_year:
            years = con.execute(
                "SELECT year(CreationDate) AS y, count(*) FROM q GROUP BY 1 ORDER BY 1"
            ).fetchall()
            chunks = [(f"year(q.CreationDate) = {y}", f"part-{y}", n) for y, n in years]
        else:
            chunks = [("true", "part-all", n_total)]
        done = rows = 0
        for where, name, n in chunks:
            sql = SELECT_SQL.format(site=site, where=where)
            con.execute(
                f"COPY ({sql}) TO '{out_dir / name}.parquet' (FORMAT parquet, COMPRESSION zstd)"
            )
            done += n
            rows += n
            reporter.update(prep_units + int((1 - PREP_SHARE) * done), rows)
            reporter._last = 0  # force the next update to be written
    except BaseException:
        reporter.finish(rows if "rows" in locals() else 0, status="failed")
        raise
    reporter.finish(rows)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sites", nargs="*")
    args = ap.parse_args()
    sites = args.sites or list(config.ALL_SITES)
    con = connect()
    counts = dict(
        con.execute("SELECT site, count(*) FROM posts WHERE PostTypeId = 1 GROUP BY 1").fetchall()
    )
    sites.sort(key=lambda s: counts.get(s, 0), reverse=True)
    progress.write_manifest(JOB, {s: counts.get(s, 1) for s in sites})
    out_root = config.PARQUET_DIR / "questions"
    for site in sites:
        t0 = time.monotonic()
        n = build_site(site, out_root, by_year=(site == config.TREATED))
        print(f"done  {site:<40} {n:>11,} questions  {time.monotonic() - t0:6.0f}s", flush=True)


if __name__ == "__main__":
    main()
