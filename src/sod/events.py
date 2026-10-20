"""Hand-curated event timeline (data/reference/events.csv)."""

from __future__ import annotations

import pandas as pd

from sod import config

EVENTS_CSV = config.REFERENCE_DIR / "events.csv"

CATEGORIES = {"ai_release", "so_policy", "so_company", "data", "external_shock"}
ROLES = {"primary_break", "secondary_break", "exclusion_window", "natural_experiment", "context"}
CONFIDENCE = {"primary", "secondary"}


def load_events() -> pd.DataFrame:
    df = pd.read_csv(EVENTS_CSV, parse_dates=["date", "end_date"], keep_default_na=True)
    return df.sort_values("date", kind="stable").reset_index(drop=True)


def break_dates() -> dict[str, pd.Timestamp]:
    """Event name -> date for the primary and secondary break dates used in the models."""
    df = load_events()
    rows = df[df["role"].isin(["primary_break", "secondary_break"])]
    return dict(zip(rows["event"], rows["date"], strict=True))


def exclusion_windows() -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    df = load_events()
    rows = df[df["role"] == "exclusion_window"]
    return [
        (r.event, r.date, r.end_date if pd.notna(r.end_date) else r.date) for r in rows.itertuples()
    ]
