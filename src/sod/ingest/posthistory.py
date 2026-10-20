"""P07: PostHistory.xml -> Parquet, keeping only the events the analysis needs.

Kept: title set/edit (1, 4), tags set/edit (3, 6), close (10), reopen (11),
delete (12), undelete (13). Close events are parsed into reason, duplicate
targets, voter count and binding reason; all free text is dropped.

Usage: python -m sod.ingest.posthistory [--workers N] [--force] [site ...]
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from sod import config, progress
from sod.ingest.xml_rows import convert_row, iter_rows, parse_tags

JOB = "posthistory"
CHUNK_ROWS = 500_000
KEEP_TYPES = {"1", "3", "4", "6", "10", "11", "12", "13"}
TAG_TYPES = {3, 6}
VOTE_TYPES = {10, 11, 12, 13}
DUPLICATE_REASONS = {1, 101}  # old "exact duplicate" and current "duplicate"

SCHEMA = pa.schema(
    [
        ("site", pa.dictionary(pa.int8(), pa.string())),
        ("Id", pa.int64()),
        ("PostHistoryTypeId", pa.int8()),
        ("PostId", pa.int64()),
        ("CreationDate", pa.timestamp("ms")),
        ("UserId", pa.int64()),
        ("tags", pa.list_(pa.string())),
        ("close_reason_id", pa.int16()),
        ("is_duplicate", pa.bool_()),
        ("duplicate_of", pa.list_(pa.int64())),
        ("n_voters", pa.int16()),
        ("binding", pa.dictionary(pa.int8(), pa.string())),
    ]
)


def _binding(value: object) -> str | None:
    """BindingReason is a string in some dumps and an object like
    {"DuplicateApprovedByAsker": ""} or {"GoldTagBadge": "python"} in others."""
    if isinstance(value, dict):
        return next(iter(value), None)
    return str(value) if value else None


def parse_close(
    comment: str | None, text: str | None
) -> tuple[int | None, bool, list[int], int, str | None]:
    """(close_reason_id, is_duplicate, duplicate_of, n_voters, binding) for a close event."""
    try:
        reason = int(comment) if comment is not None else None
    except ValueError:
        reason = None
    try:
        payload = json.loads(text) if text else {}
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    voters = payload.get("Voters") or []
    binding = next(
        (_binding(v.get("BindingReason")) for v in voters if v.get("BindingReason")), None
    )
    dup_of = [int(x) for x in payload.get("OriginalQuestionIds") or []]
    return reason, reason in DUPLICATE_REASONS, dup_of, len(voters), binding


def ingest_site(site_dir: Path, out_root: Path, job: str = JOB, force: bool = False) -> dict:
    site = site_dir.name
    out_dir = out_root / f"site={site}"
    marker = out_dir / "_SUCCESS.json"
    xml = site_dir / "PostHistory.xml"
    total_bytes = xml.stat().st_size

    if marker.exists() and not force:
        stats = json.loads(marker.read_text())
        progress.Reporter(job, site, total_bytes).finish(stats["rows_read"])
        return stats
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    reporter = progress.Reporter(job, site, total_bytes)
    t0 = time.monotonic()
    buf: dict[str, list] = {n: [] for n in SCHEMA.names}
    part = read = kept = bad_reason = 0
    by_type: Counter[str] = Counter()
    by_reason: Counter[str] = Counter()

    def flush() -> None:
        nonlocal buf, part
        pq.write_table(
            pa.Table.from_pydict(buf, schema=SCHEMA),
            out_dir / f"part-{part:05d}.parquet",
            compression="zstd",
        )
        buf, part = {n: [] for n in SCHEMA.names}, part + 1

    try:
        with xml.open("rb") as f:
            reader = progress.CountingReader(f)
            for raw in iter_rows(reader):
                read += 1
                t = raw.get("PostHistoryTypeId")
                by_type[t] += 1
                if read % 20_000 == 0:
                    reporter.update(reader.bytes_read, read)
                if t not in KEEP_TYPES:
                    continue
                r = convert_row("PostHistory", raw)
                ptype = r["PostHistoryTypeId"]
                reason, is_dup, dup_of, n_voters, binding = (None, None, None, None, None)
                if ptype in VOTE_TYPES:
                    reason, is_dup, dup_of, n_voters, binding = parse_close(r["Comment"], r["Text"])
                    if ptype != 10:
                        reason, is_dup, dup_of = None, None, None
                    elif reason is None:
                        bad_reason += 1
                    else:
                        by_reason[str(reason)] += 1
                buf["site"].append(site)
                buf["Id"].append(r["Id"])
                buf["PostHistoryTypeId"].append(ptype)
                buf["PostId"].append(r["PostId"])
                buf["CreationDate"].append(r["CreationDate"])
                buf["UserId"].append(r["UserId"])
                buf["tags"].append(parse_tags(r["Text"]) if ptype in TAG_TYPES else None)
                buf["close_reason_id"].append(reason)
                buf["is_duplicate"].append(is_dup)
                buf["duplicate_of"].append(dup_of)
                buf["n_voters"].append(n_voters)
                buf["binding"].append(binding)
                kept += 1
                if kept % CHUNK_ROWS == 0:
                    flush()
        if buf["site"] or part == 0:
            flush()
    except BaseException:
        reporter.finish(read, status="failed")
        raise

    stats = {
        "site": site,
        "rows_read": read,
        "rows_kept": kept,
        "count_by_type": dict(sorted(by_type.items(), key=lambda kv: int(kv[0]))),
        "close_reasons": dict(sorted(by_reason.items(), key=lambda kv: int(kv[0]))),
        "close_events_without_reason": bad_reason,
        "seconds": round(time.monotonic() - t0, 1),
        "xml_bytes": total_bytes,
        "parquet_bytes": sum(p.stat().st_size for p in out_dir.glob("*.parquet")),
    }
    marker.write_text(json.dumps(stats, indent=2))
    reporter.finish(read)
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sites", nargs="*")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    dirs = [config.RAW_DIR / s for s in (args.sites or config.ALL_SITES)]
    dirs.sort(key=lambda d: (d / "PostHistory.xml").stat().st_size, reverse=True)
    out_root = config.PARQUET_DIR / "posthistory"
    out_root.mkdir(parents=True, exist_ok=True)
    progress.write_manifest(JOB, {d.name: (d / "PostHistory.xml").stat().st_size for d in dirs})

    failures = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(ingest_site, d, out_root, JOB, args.force): d.name for d in dirs}
        for fut in as_completed(futures):
            site = futures[fut]
            try:
                s = fut.result()
                print(
                    f"done  {site:<40} {s['rows_read']:>12,} read  {s['rows_kept']:>11,} kept"
                    f"  {s['seconds']:>7.0f}s",
                    flush=True,
                )
            except Exception as e:
                failures.append(site)
                print(f"FAIL  {site}: {type(e).__name__}: {e}", flush=True)
    if failures:
        raise SystemExit(f"failed sites: {failures}")


if __name__ == "__main__":
    main()
