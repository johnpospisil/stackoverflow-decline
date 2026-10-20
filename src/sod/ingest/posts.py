"""P05: Posts.xml -> Parquet for every site.

Output: <PARQUET_DIR>/posts/site=<site>/part-NNNNN.parquet plus _SUCCESS.json (stats).
Raw text (Body, Title) and user names are dropped after computing numeric features.
Known watermark rows (Id >= 1e9) are excluded and logged.

Usage: python -m sod.ingest.posts [--workers N] [--force] [site ...]
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from array import array
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from sod import config, progress
from sod.ingest.body_features import body_features, title_features
from sod.ingest.xml_rows import convert_row, iter_rows, parse_tags

JOB = "posts"
CHUNK_ROWS = 250_000
WATERMARK_MIN_ID = 1_000_000_000

SCHEMA = pa.schema(
    [
        ("site", pa.dictionary(pa.int8(), pa.string())),
        ("Id", pa.int64()),
        ("PostTypeId", pa.int8()),
        ("ParentId", pa.int64()),
        ("AcceptedAnswerId", pa.int64()),
        ("CreationDate", pa.timestamp("ms")),
        ("Score", pa.int32()),
        ("ViewCount", pa.int64()),
        ("OwnerUserId", pa.int64()),
        ("owner_deleted", pa.bool_()),
        ("LastEditorUserId", pa.int64()),
        ("LastEditDate", pa.timestamp("ms")),
        ("LastActivityDate", pa.timestamp("ms")),
        ("tags", pa.list_(pa.string())),
        ("n_tags", pa.int8()),
        ("AnswerCount", pa.int32()),
        ("CommentCount", pa.int32()),
        ("FavoriteCount", pa.int32()),
        ("ClosedDate", pa.timestamp("ms")),
        ("CommunityOwnedDate", pa.timestamp("ms")),
        ("ContentLicense", pa.dictionary(pa.int8(), pa.string())),
        ("body_chars", pa.int32()),
        ("text_chars", pa.int32()),
        ("code_chars", pa.int32()),
        ("n_code_blocks", pa.int16()),
        ("n_inline_code", pa.int16()),
        ("n_links", pa.int16()),
        ("n_images", pa.int16()),
        ("title_chars", pa.int16()),
        ("title_words", pa.int16()),
    ]
)
COPY_COLS = [
    "Id",
    "PostTypeId",
    "ParentId",
    "AcceptedAnswerId",
    "CreationDate",
    "Score",
    "ViewCount",
    "OwnerUserId",
    "LastEditorUserId",
    "LastEditDate",
    "LastActivityDate",
    "AnswerCount",
    "CommentCount",
    "FavoriteCount",
    "ClosedDate",
    "CommunityOwnedDate",
    "ContentLicense",
]


def _new_buffer() -> dict[str, list]:
    return {name: [] for name in SCHEMA.names}


def _flush(buf: dict[str, list], out_dir: Path, part: int) -> None:
    table = pa.Table.from_pydict(buf, schema=SCHEMA)
    pq.write_table(table, out_dir / f"part-{part:05d}.parquet", compression="zstd")


def ingest_site(site_dir: Path, out_root: Path, job: str = JOB, force: bool = False) -> dict:
    site = site_dir.name
    out_dir = out_root / f"site={site}"
    marker = out_dir / "_SUCCESS.json"
    xml = site_dir / "Posts.xml"
    total_bytes = xml.stat().st_size

    if marker.exists() and not force:
        stats = json.loads(marker.read_text())
        progress.Reporter(job, site, total_bytes).finish(stats["rows"])
        return stats
    if out_dir.exists():
        shutil.rmtree(out_dir)  # partial output from an interrupted run
    out_dir.mkdir(parents=True)

    reporter = progress.Reporter(job, site, total_bytes)
    t0 = time.monotonic()
    buf, part, rows = _new_buffer(), 0, 0
    ids = array("q")
    by_type: Counter[str] = Counter()
    watermark_ids: list[int] = []
    owner_minus1_qa: list[int] = []
    min_q = max_q = None

    try:
        with xml.open("rb") as f:
            reader = progress.CountingReader(f)
            for raw in iter_rows(reader):
                r = convert_row("Posts", raw)
                pid = r["Id"]
                if pid >= WATERMARK_MIN_ID:
                    watermark_ids.append(pid)
                    continue
                ptype = r["PostTypeId"]
                if ptype in (1, 2) and r["OwnerUserId"] == -1:
                    owner_minus1_qa.append(pid)
                if ptype == 1:
                    cd = r["CreationDate"]
                    min_q = cd if min_q is None or cd < min_q else min_q
                    max_q = cd if max_q is None or cd > max_q else max_q

                tags = parse_tags(r["Tags"])
                buf["site"].append(site)
                for col in COPY_COLS:
                    buf[col].append(r[col])
                buf["owner_deleted"].append(r["OwnerUserId"] is None)
                buf["tags"].append(tags)
                buf["n_tags"].append(len(tags))
                for k, v in body_features(r["Body"]).items():
                    buf[k].append(v)
                for k, v in title_features(r["Title"]).items():
                    buf[k].append(v)

                ids.append(pid)
                by_type[str(ptype)] += 1
                rows += 1
                if rows % CHUNK_ROWS == 0:
                    _flush(buf, out_dir, part)
                    buf, part = _new_buffer(), part + 1
                    reporter.update(reader.bytes_read, rows)
                elif rows % 5000 == 0:
                    reporter.update(reader.bytes_read, rows)
        if buf["Id"]:
            _flush(buf, out_dir, part)
    except BaseException:
        reporter.finish(rows, status="failed")
        raise

    id_arr = np.frombuffer(ids, dtype=np.int64)
    stats = {
        "site": site,
        "rows": rows,
        "rows_by_type": dict(sorted(by_type.items(), key=lambda kv: int(kv[0]))),
        "duplicate_ids": int(id_arr.size - np.unique(id_arr).size),
        "min_question_date": min_q.isoformat() if min_q else None,
        "max_question_date": max_q.isoformat() if max_q else None,
        "watermark_ids_excluded": watermark_ids,
        "owner_minus1_qa_ids": owner_minus1_qa,
        "seconds": round(time.monotonic() - t0, 1),
        "xml_bytes": total_bytes,
        "parquet_bytes": sum(p.stat().st_size for p in out_dir.glob("*.parquet")),
    }
    marker.write_text(json.dumps(stats, indent=2))
    reporter.finish(rows)
    return stats


def _site_dirs(names: list[str]) -> list[Path]:
    sites = names or list(config.ALL_SITES)
    dirs = [config.RAW_DIR / s for s in sites]
    # Largest first, so Stack Overflow starts immediately and the rest fill in around it.
    return sorted(dirs, key=lambda d: (d / "Posts.xml").stat().st_size, reverse=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sites", nargs="*")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    dirs = _site_dirs(args.sites)
    out_root = config.PARQUET_DIR / "posts"
    out_root.mkdir(parents=True, exist_ok=True)
    progress.write_manifest(JOB, {d.name: (d / "Posts.xml").stat().st_size for d in dirs})

    failures = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(ingest_site, d, out_root, JOB, args.force): d.name for d in dirs}
        for fut in as_completed(futures):
            site = futures[fut]
            try:
                s = fut.result()
                print(f"done  {site:<40} {s['rows']:>11,} rows  {s['seconds']:>7.0f}s", flush=True)
            except Exception as e:  # keep going; report at the end
                failures.append(site)
                print(f"FAIL  {site}: {type(e).__name__}: {e}", flush=True)
    if failures:
        raise SystemExit(f"failed sites: {failures}")


if __name__ == "__main__":
    main()
