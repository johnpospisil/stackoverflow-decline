import pandas as pd

from sod import config, events


def test_schema_and_values():
    df = events.load_events()
    assert list(df.columns) == [
        "date",
        "end_date",
        "precision",
        "event",
        "category",
        "role",
        "source_url",
        "confidence",
        "notes",
    ]
    assert set(df["category"]) <= events.CATEGORIES
    assert set(df["role"]) <= events.ROLES
    assert set(df["confidence"]) <= events.CONFIDENCE
    assert set(df["precision"]) <= {"day", "month"}
    assert df["source_url"].str.startswith("https://").all()
    assert not df["event"].duplicated().any()


def test_windows_end_after_start():
    df = events.load_events()
    windows = df.dropna(subset=["end_date"])
    assert (windows["end_date"] > windows["date"]).all()


def test_chatgpt_is_the_only_primary_break_and_matches_config():
    df = events.load_events()
    primary = df[df["role"] == "primary_break"]
    assert len(primary) == 1
    assert primary["date"].iloc[0] == pd.Timestamp(config.BREAK_DATE)


def test_events_within_study_period():
    df = events.load_events()
    assert df["date"].min() >= pd.Timestamp("2008-01-01")
    assert df["date"].max() <= pd.Timestamp(config.DUMP_CUTOFF)
