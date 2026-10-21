"""P13: site x period and tag x period panels (period = week and month).

Outputs in <DATA_DIR>/panels/ as Parquet and CSV:
  site_week, site_month   all 27 sites
  tag_week,  tag_month    Stack Overflow: top 300 tags + 69 post-2021 tags (tags at time of asking)

Counts are stored next to their denominators so any rate can be recomputed:
  questions, answers, new_posters (first question or answer), active_askers, active_answerers,
  answered_ever (as of the dump; recent periods are not comparable),
  eligible_24h / answered_24h, eligible_7d / answered_7d, eligible_30d / accepted_30d
    (fixed-window outcomes, decided 2026-10-21: a question counts only if the whole window
    ends before the 2026-09-30 cut-off; acceptance dated by the acceptance vote, day precision),
  closed, closed_duplicate, median_hours_to_first_answer.
site_month also has questions_incl_deleted from SEDE (robustness check 8).
Flags: partial_period (period not fully covered by the dump), final_8_weeks (answers and
closures still arriving).

Usage: python -m sod.build.panels
"""

from __future__ import annotations

import time
from datetime import timedelta
from pathlib import Path

import pandas as pd

from sod import config, progress
from sod.db import connect

JOB = "panels"
CUTOFF_END = config.DUMP_CUTOFF + timedelta(days=1)  # exclusive upper bound
FINAL_8W_START = CUTOFF_END - timedelta(weeks=8)
STEPS = ("prep", "site_week", "site_month", "tag_week", "tag_month", "export")


def _prep(con) -> None:
    pq_dir = config.PARQUET_DIR
    top_csv = config.REFERENCE_DIR / "tag_features.csv"
    new_csv = config.REFERENCE_DIR / "tags_new_post2021.csv"
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE qx AS
        SELECT q.*, p.AcceptedAnswerId
        FROM read_parquet('{pq_dir}/questions/*/*.parquet') q
        JOIN (SELECT site, Id, AcceptedAnswerId FROM posts WHERE PostTypeId = 1) p
          ON p.site = q.site AND p.Id = q.Id;

        CREATE OR REPLACE TEMP TABLE accept AS
        SELECT site, PostId AS answer_id, min(CreationDate) AS accepted_on
        FROM votes WHERE VoteTypeId = 1 GROUP BY 1, 2;

        CREATE OR REPLACE TEMP TABLE qf AS
        SELECT qx.*,
               CreationDate < TIMESTAMP '{CUTOFF_END}' - INTERVAL 1 DAY AS eligible_24h,
               coalesce(hours_to_first_answer <= 24, false) AS answered_24h,
               CreationDate < TIMESTAMP '{CUTOFF_END}' - INTERVAL 7 DAY AS eligible_7d,
               coalesce(hours_to_first_answer <= 24 * 7, false) AS answered_7d,
               CreationDate < TIMESTAMP '{CUTOFF_END}' - INTERVAL 30 DAY AS eligible_30d,
               coalesce(a.accepted_on <= CreationDate::DATE + INTERVAL 30 DAY, false)
                   AS accepted_30d
        FROM qx LEFT JOIN accept a ON a.site = qx.site AND a.answer_id = qx.AcceptedAnswerId;

        CREATE OR REPLACE TEMP TABLE ans AS
        SELECT site, OwnerUserId, CreationDate FROM posts WHERE PostTypeId = 2;

        CREATE OR REPLACE TEMP TABLE newp AS
        SELECT site, first_post_at FROM read_parquet('{pq_dir}/user_summary/*/*.parquet');

        CREATE OR REPLACE TEMP TABLE tagset AS
        SELECT tag, 'top300' AS tag_group, family AS tag_kind
        FROM read_csv('{top_csv}')
        UNION ALL
        SELECT tag, 'new_post2021', kind FROM read_csv('{new_csv}');
        """
    )


QUESTION_METRICS = """
    count(*)::INTEGER AS questions,
    count(DISTINCT OwnerUserId)::INTEGER AS active_askers,
    count(*) FILTER (WHERE n_answers > 0)::INTEGER AS answered_ever,
    count(*) FILTER (WHERE eligible_24h)::INTEGER AS eligible_24h,
    count(*) FILTER (WHERE eligible_24h AND answered_24h)::INTEGER AS answered_24h,
    count(*) FILTER (WHERE eligible_7d)::INTEGER AS eligible_7d,
    count(*) FILTER (WHERE eligible_7d AND answered_7d)::INTEGER AS answered_7d,
    count(*) FILTER (WHERE eligible_30d)::INTEGER AS eligible_30d,
    count(*) FILTER (WHERE eligible_30d AND accepted_30d)::INTEGER AS accepted_30d,
    count(*) FILTER (WHERE ever_closed)::INTEGER AS closed,
    count(*) FILTER (WHERE closed_as_duplicate)::INTEGER AS closed_duplicate,
    count(*) FILTER (WHERE has_code)::INTEGER AS with_code,
    median(hours_to_first_answer) AS median_hours_to_first_answer
"""


def _flags(period: str) -> str:
    length = "INTERVAL 7 DAY" if period == "week" else "INTERVAL 1 MONTH"
    return f"""
        period + {length} > DATE '{CUTOFF_END}' OR period < DATE '2008-07-31' AS partial_period,
        period + {length} > DATE '{FINAL_8W_START}' AS final_8_weeks
    """


def site_panel(con, period: str) -> pd.DataFrame:
    trunc = f"date_trunc('{period}', CreationDate)::DATE"
    return con.execute(
        f"""
        WITH q AS (
            SELECT site, {trunc} AS period, {QUESTION_METRICS} FROM qf GROUP BY 1, 2
        ),
        a AS (
            SELECT site, {trunc} AS period, count(*)::INTEGER AS answers,
                   count(DISTINCT OwnerUserId)::INTEGER AS active_answerers
            FROM ans GROUP BY 1, 2
        ),
        n AS (
            SELECT site, date_trunc('{period}', first_post_at)::DATE AS period,
                   count(*)::INTEGER AS new_posters
            FROM newp GROUP BY 1, 2
        )
        SELECT site, period, q.* EXCLUDE (site, period),
               coalesce(a.answers, 0) AS answers,
               coalesce(a.active_answerers, 0) AS active_answerers,
               coalesce(n.new_posters, 0) AS new_posters,
               {_flags(period)}
        FROM q FULL JOIN a USING (site, period) FULL JOIN n USING (site, period)
        ORDER BY site, period
        """
    ).df()


def tag_panel(con, period: str) -> pd.DataFrame:
    trunc = f"date_trunc('{period}', CreationDate)::DATE"
    return (
        con.execute(
            f"""
        WITH t AS (
            SELECT qf.*, unnest(tags) AS tag FROM qf WHERE site = '{config.TREATED}'
        )
        SELECT tag, any_value(ts.tag_group) AS tag_group, any_value(ts.tag_kind) AS tag_kind,
               {trunc} AS period, {QUESTION_METRICS}
        FROM t JOIN tagset ts USING (tag)
        GROUP BY tag, period
        ORDER BY tag, period
        """
        )
        .df()
        .assign(
            partial_period=lambda d: _flag_series(d["period"], period, "partial"),
            final_8_weeks=lambda d: _flag_series(d["period"], period, "final"),
        )
    )


def _flag_series(periods: pd.Series, period: str, kind: str) -> pd.Series:
    start = pd.to_datetime(periods).astype("datetime64[ns]")
    if start.empty:
        return pd.Series([], dtype=bool, index=periods.index)
    end = start + (pd.DateOffset(days=7) if period == "week" else pd.DateOffset(months=1))
    if kind == "partial":
        return end > pd.Timestamp(CUTOFF_END)
    return end > pd.Timestamp(FINAL_8W_START)


def complete(df: pd.DataFrame, key: str, period: str) -> pd.DataFrame:
    """One row per key x period from the key's first period to the last full or partial
    period before the cut-off, with zero counts where nothing happened. Medians stay NaN."""
    if df.empty:
        return df
    freq = "W-MON" if period == "week" else "MS"
    last = pd.Timestamp(config.DUMP_CUTOFF).to_period("W" if period == "week" else "M")
    last = last.start_time.normalize()
    static = [c for c in ("tag_group", "tag_kind") if c in df.columns]
    parts = []
    for k, g in df.groupby(key, sort=False):
        idx = pd.date_range(g["period"].min(), last, freq=freq, name="period")
        g = g.set_index("period").reindex(idx).reset_index()
        g[key] = k
        for c in static:
            g[c] = g[c].dropna().iloc[0]
        parts.append(g)
    out = pd.concat(parts, ignore_index=True)
    counts = [
        c
        for c in out.columns
        if out[c].dtype.kind in "iuf"
        and c != "median_hours_to_first_answer"
        and c != "questions_incl_deleted"
    ]
    out[counts] = out[counts].fillna(0).astype("int64")
    out["partial_period"] = _flag_series(out["period"], period, "partial")
    out["final_8_weeks"] = _flag_series(out["period"], period, "final")
    return out.sort_values([key, "period"]).reset_index(drop=True)


def add_sede(site_month: pd.DataFrame) -> pd.DataFrame:
    from sod.build.sede import load_sede

    sede = load_sede()[["site", "month", "total"]].rename(
        columns={"month": "period", "total": "questions_incl_deleted"}
    )
    return site_month.merge(sede, on=["site", "period"], how="left")


def build(out_dir: Path, job: str = JOB, with_sede: bool = True) -> dict[str, pd.DataFrame]:
    con = connect()
    rep = progress.Reporter(job, "panels", len(STEPS))
    panels: dict[str, pd.DataFrame] = {}
    try:
        _prep(con)
        rep._last = 0
        rep.update(1, 0)
        for i, name in enumerate(STEPS[1:5], start=2):
            kind, period = name.split("_")
            df = site_panel(con, period) if kind == "site" else tag_panel(con, period)
            df["period"] = pd.to_datetime(df["period"]).astype("datetime64[ns]")
            panels[name] = complete(df, kind, period)
            rep._last = 0
            rep.update(i, sum(len(p) for p in panels.values()))
        if with_sede:
            panels["site_month"] = add_sede(panels["site_month"])
        out_dir.mkdir(parents=True, exist_ok=True)
        for name, df in panels.items():
            df.to_parquet(out_dir / f"{name}.parquet", index=False)
            df.to_csv(out_dir / f"{name}.csv", index=False)
    except BaseException:
        rep.finish(0, status="failed")
        raise
    rep.finish(sum(len(p) for p in panels.values()))
    return panels


def main() -> None:
    progress.write_manifest(JOB, {"panels": len(STEPS)})
    t0 = time.monotonic()
    panels = build(config.PANEL_DIR)
    for name, df in panels.items():
        print(f"{name:<11} {len(df):>9,} rows", flush=True)
    print(f"done in {time.monotonic() - t0:.0f}s")


if __name__ == "__main__":
    main()
