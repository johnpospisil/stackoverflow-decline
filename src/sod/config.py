"""Project paths and constants.

Paths come from environment variables so nothing machine-specific is hard-coded
in the pipeline. The defaults match the author's setup (see DATA.md).
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = Path(os.environ.get("SOD_RAW_DIR", "/Volumes/Drive3/data"))
DATA_DIR = Path(os.environ.get("SOD_DATA_DIR", "/Volumes/Drive3/sod"))

PARQUET_DIR = DATA_DIR / "parquet"
PANEL_DIR = DATA_DIR / "panels"
MODEL_DIR = DATA_DIR / "models"
DUCKDB_PATH = DATA_DIR / "sod.duckdb"

REFERENCE_DIR = REPO_ROOT / "data" / "reference"
FIGURE_DIR = REPO_ROOT / "report" / "figures"

DUMP_RELEASE = "2026-Q3"
DUMP_CUTOFF = date(2026, 9, 30)
BREAK_DATE = date(2022, 11, 30)  # ChatGPT release
BREAK_WEEK = date(2022, 11, 28)  # Monday of the release week

XML_TABLES = (
    "Posts",
    "Users",
    "Votes",
    "Comments",
    "PostHistory",
    "PostLinks",
    "Tags",
    "Badges",
)

TREATED = "stackoverflow.com"

SITE_GROUPS: dict[str, tuple[str, ...]] = {
    "treated": (TREATED,),
    "so_language": (
        "ru.stackoverflow.com",
        "es.stackoverflow.com",
        "pt.stackoverflow.com",
        "ja.stackoverflow.com",
    ),
    "tech_exposed": (
        "superuser.com",
        "serverfault.com",
        "askubuntu.com",
        "unix.stackexchange.com",
        "softwareengineering.stackexchange.com",
        "dba.stackexchange.com",
    ),
    "donor": (
        "math.stackexchange.com",
        "physics.stackexchange.com",
        "chemistry.stackexchange.com",
        "biology.stackexchange.com",
        "english.stackexchange.com",
        "philosophy.stackexchange.com",
        "history.stackexchange.com",
        "cooking.stackexchange.com",
        "diy.stackexchange.com",
        "travel.stackexchange.com",
        "bicycles.stackexchange.com",
        "gaming.stackexchange.com",
        "scifi.stackexchange.com",
        "movies.stackexchange.com",
        "rpg.stackexchange.com",
    ),
    "context": ("meta.stackoverflow.com",),
}

ALL_SITES: tuple[str, ...] = tuple(s for group in SITE_GROUPS.values() for s in group)


def site_group(site: str) -> str:
    for group, sites in SITE_GROUPS.items():
        if site in sites:
            return group
    raise KeyError(f"unknown site: {site}")
