"""P06: Users, Votes, Comments, PostLinks and Tags -> Parquet for every site.

Output: <PARQUET_DIR>/<table>/site=<site>/part-NNNNN.parquet plus _SUCCESS.json.
Personal text (names, locations, bios, comment text) is reduced to flags or lengths.

Usage: python -m sod.ingest.tables [--workers N] [--force] [--tables T ...] [site ...]
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from sod import config, progress
from sod.ingest.xml_rows import convert_row, iter_rows

JOB = "tables"
CHUNK_ROWS = 500_000
SITE_TYPE = pa.dictionary(pa.int8(), pa.string())


@dataclass(frozen=True)
class TableSpec:
    schema: pa.Schema
    copy: tuple[str, ...]  # columns copied unchanged from the converted row
    derive: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    count_by: str | None = None  # column to tally in the stats (e.g. VoteTypeId)
    date_col: str | None = "CreationDate"


def _users(r: dict) -> dict:
    return {"has_location": bool(r["Location"]), "has_website": bool(r["WebsiteUrl"])}


def _comments(r: dict) -> dict:
    return {"text_chars": len(r["Text"] or ""), "user_deleted": r["UserId"] is None}


SPECS: dict[str, TableSpec] = {
    "Users": TableSpec(
        schema=pa.schema(
            [
                ("site", SITE_TYPE),
                ("Id", pa.int64()),
                ("CreationDate", pa.timestamp("ms")),
                ("Reputation", pa.int64()),
                ("LastAccessDate", pa.timestamp("ms")),
                ("Views", pa.int64()),
                ("UpVotes", pa.int64()),
                ("DownVotes", pa.int64()),
                ("AccountId", pa.int64()),
                ("has_location", pa.bool_()),
                ("has_website", pa.bool_()),
            ]
        ),
        copy=(
            "Id",
            "CreationDate",
            "Reputation",
            "LastAccessDate",
            "Views",
            "UpVotes",
            "DownVotes",
            "AccountId",
        ),
        derive=_users,
    ),
    "Votes": TableSpec(
        schema=pa.schema(
            [
                ("site", SITE_TYPE),
                ("Id", pa.int64()),
                ("PostId", pa.int64()),
                ("VoteTypeId", pa.int8()),
                ("UserId", pa.int64()),
                ("CreationDate", pa.timestamp("ms")),
                ("BountyAmount", pa.int32()),
            ]
        ),
        copy=("Id", "PostId", "VoteTypeId", "UserId", "CreationDate", "BountyAmount"),
        count_by="VoteTypeId",
    ),
    "Comments": TableSpec(
        schema=pa.schema(
            [
                ("site", SITE_TYPE),
                ("Id", pa.int64()),
                ("PostId", pa.int64()),
                ("Score", pa.int32()),
                ("CreationDate", pa.timestamp("ms")),
                ("UserId", pa.int64()),
                ("text_chars", pa.int32()),
                ("user_deleted", pa.bool_()),
            ]
        ),
        copy=("Id", "PostId", "Score", "CreationDate", "UserId"),
        derive=_comments,
    ),
    "PostLinks": TableSpec(
        schema=pa.schema(
            [
                ("site", SITE_TYPE),
                ("Id", pa.int64()),
                ("CreationDate", pa.timestamp("ms")),
                ("PostId", pa.int64()),
                ("RelatedPostId", pa.int64()),
                ("LinkTypeId", pa.int8()),
            ]
        ),
        copy=("Id", "CreationDate", "PostId", "RelatedPostId", "LinkTypeId"),
        count_by="LinkTypeId",
    ),
    "Tags": TableSpec(
        schema=pa.schema(
            [
                ("site", SITE_TYPE),
                ("Id", pa.int64()),
                ("TagName", pa.string()),
                ("Count", pa.int64()),
                ("ExcerptPostId", pa.int64()),
                ("WikiPostId", pa.int64()),
                ("IsModeratorOnly", pa.bool_()),
                ("IsRequired", pa.bool_()),
            ]
        ),
        copy=(
            "Id",
            "TagName",
            "Count",
            "ExcerptPostId",
            "WikiPostId",
            "IsModeratorOnly",
            "IsRequired",
        ),
        date_col=None,
    ),
}


def ingest_table(
    site_dir: Path, table: str, out_root: Path, job: str = JOB, force: bool = False
) -> dict:
    spec = SPECS[table]
    site = site_dir.name
    task = f"{site}:{table}"
    out_dir = out_root / f"site={site}"
    marker = out_dir / "_SUCCESS.json"
    xml = site_dir / f"{table}.xml"
    total_bytes = xml.stat().st_size

    if marker.exists() and not force:
        stats = json.loads(marker.read_text())
        progress.Reporter(job, task, total_bytes).finish(stats["rows"])
        return stats
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    reporter = progress.Reporter(job, task, total_bytes)
    t0 = time.monotonic()
    names = spec.schema.names
    buf: dict[str, list] = {n: [] for n in names}
    part = rows = with_user = 0
    counts: Counter[str] = Counter()
    min_d = max_d = None

    def flush() -> None:
        nonlocal buf, part
        pq.write_table(
            pa.Table.from_pydict(buf, schema=spec.schema),
            out_dir / f"part-{part:05d}.parquet",
            compression="zstd",
        )
        buf, part = {n: [] for n in names}, part + 1

    try:
        with xml.open("rb") as f:
            reader = progress.CountingReader(f)
            for raw in iter_rows(reader):
                r = convert_row(table, raw)
                buf["site"].append(site)
                for col in spec.copy:
                    buf[col].append(r[col])
                if spec.derive:
                    for k, v in spec.derive(r).items():
                        buf[k].append(v)
                if spec.count_by:
                    counts[str(r[spec.count_by])] += 1
                if "UserId" in r and r["UserId"] is not None:
                    with_user += 1
                if spec.date_col and (d := r[spec.date_col]) is not None:
                    min_d = d if min_d is None or d < min_d else min_d
                    max_d = d if max_d is None or d > max_d else max_d
                rows += 1
                if rows % CHUNK_ROWS == 0:
                    flush()
                if rows % 10_000 == 0:
                    reporter.update(reader.bytes_read, rows)
        if buf["site"] or part == 0:
            flush()
    except BaseException:
        reporter.finish(rows, status="failed")
        raise

    stats = {
        "site": site,
        "table": table,
        "rows": rows,
        "count_by": dict(sorted(counts.items(), key=lambda kv: int(kv[0]))) if counts else None,
        "rows_with_user": with_user,
        "min_date": min_d.isoformat() if min_d else None,
        "max_date": max_d.isoformat() if max_d else None,
        "seconds": round(time.monotonic() - t0, 1),
        "xml_bytes": total_bytes,
        "parquet_bytes": sum(p.stat().st_size for p in out_dir.glob("*.parquet")),
    }
    marker.write_text(json.dumps(stats, indent=2))
    reporter.finish(rows)
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sites", nargs="*")
    ap.add_argument("--tables", nargs="*", default=list(SPECS))
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    sites = args.sites or list(config.ALL_SITES)
    jobs = [(config.RAW_DIR / s, t) for s in sites for t in args.tables]
    # Largest files first so the long Stack Overflow tables start immediately.
    jobs.sort(key=lambda st: (st[0] / f"{st[1]}.xml").stat().st_size, reverse=True)
    progress.write_manifest(
        JOB, {f"{d.name}:{t}": (d / f"{t}.xml").stat().st_size for d, t in jobs}
    )

    failures = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                ingest_table, d, t, config.PARQUET_DIR / t.lower(), JOB, args.force
            ): f"{d.name}:{t}"
            for d, t in jobs
        }
        for fut in as_completed(futures):
            task = futures[fut]
            try:
                s = fut.result()
                print(f"done  {task:<50} {s['rows']:>13,} rows  {s['seconds']:>7.0f}s", flush=True)
            except Exception as e:
                failures.append(task)
                print(f"FAIL  {task}: {type(e).__name__}: {e}", flush=True)
    if failures:
        raise SystemExit(f"failed: {failures}")


if __name__ == "__main__":
    main()
