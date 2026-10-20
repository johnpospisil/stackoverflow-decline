"""Hash the raw dump archives (MD5, SHA-1, SHA-256 in one pass) for provenance checks.

Usage: python -m sod.ingest.checksums [OUT_CSV]
Writes data/reference/dump_checksums.csv by default.
"""

from __future__ import annotations

import csv
import hashlib
import sys
import time
from pathlib import Path

from sod import config

CHUNK = 8 * 1024 * 1024


def hash_file(path: Path) -> dict[str, str]:
    hashes = {name: hashlib.new(name) for name in ("md5", "sha1", "sha256")}
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            for h in hashes.values():
                h.update(chunk)
    return {name: h.hexdigest() for name, h in hashes.items()}


def main(out: Path) -> None:
    archives = sorted(config.RAW_DIR.glob("*.7z"), key=lambda p: p.stat().st_size)
    rows = []
    for path in archives:
        start = time.monotonic()
        digests = hash_file(path)
        secs = time.monotonic() - start
        size = path.stat().st_size
        rows.append({"file": path.name, "bytes": size, **digests})
        print(f"{path.name:<45} {size / 1e9:7.2f} GB  {secs:6.0f}s  {digests['md5']}", flush=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "bytes", "md5", "sha1", "sha256"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else config.REFERENCE_DIR / "dump_checksums.csv")
