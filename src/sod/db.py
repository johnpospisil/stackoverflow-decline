"""DuckDB connection with one view per ingested table (all sites, Parquet on Drive3)."""

from __future__ import annotations

import duckdb

from sod import config

TABLES = ("posts", "users", "votes", "comments", "postlinks", "tags", "posthistory")


def connect(memory_limit: str = "8GB") -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    try:
        con.execute("SET enable_progress_bar = false")
    except duckdb.InvalidInputException:
        pass  # inside Jupyter without ipywidgets the bar is already off
    con.execute(f"SET memory_limit = '{memory_limit}'")
    tmp = config.DATA_DIR / "duckdb_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    con.execute(f"SET temp_directory = '{tmp}'")
    for t in TABLES:
        path = config.PARQUET_DIR / t
        if path.exists():
            con.execute(
                f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{path}/*/*.parquet', "
                "hive_partitioning = false)"
            )
    return con
