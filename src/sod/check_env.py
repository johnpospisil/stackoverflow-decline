"""`make check-env`: confirm the raw dump is reachable and there is room to work."""

from __future__ import annotations

import shutil
import sys

from sod import config

MIN_FREE_GB = 100


def main() -> int:
    problems: list[str] = []

    print(f"Python      {sys.version.split()[0]}")
    print(f"Raw dir     {config.RAW_DIR}")
    print(f"Data dir    {config.DATA_DIR}")

    if not config.RAW_DIR.is_dir():
        print("\nRaw dir not found. Is the external drive mounted?")
        return 1

    missing_sites = [s for s in config.ALL_SITES if not (config.RAW_DIR / s).is_dir()]
    missing_tables = [
        f"{s}/{t}.xml"
        for s in config.ALL_SITES
        if s not in missing_sites
        for t in config.XML_TABLES
        if not (config.RAW_DIR / s / f"{t}.xml").is_file()
    ]
    found = len(config.ALL_SITES) - len(missing_sites)
    print(f"Sites       {found}/{len(config.ALL_SITES)} present")
    if missing_sites:
        problems.append(f"missing sites: {', '.join(missing_sites)}")
    if missing_tables:
        problems.append(f"missing tables: {', '.join(missing_tables)}")

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    for label, path in (("Raw disk", config.RAW_DIR), ("Data disk", config.DATA_DIR)):
        free_gb = shutil.disk_usage(path).free / 1e9
        print(f"{label:<11} {free_gb:,.0f} GB free")
        if free_gb < MIN_FREE_GB:
            problems.append(f"{label.lower()} has under {MIN_FREE_GB} GB free")

    if problems:
        print("\nPROBLEMS:\n  - " + "\n  - ".join(problems))
        return 1
    print("\nOK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
