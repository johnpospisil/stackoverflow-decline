import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from sod.ingest import tables

FIXTURE_SITE = Path(__file__).parent / "fixtures" / "sample.stackexchange.com"


@pytest.fixture()
def run(tmp_path, monkeypatch):
    monkeypatch.setattr(tables.progress, "PROGRESS_DIR", tmp_path / "progress")

    def _run(table: str):
        out_root = tmp_path / table.lower()
        stats = tables.ingest_table(FIXTURE_SITE, table, out_root, job="test")
        rows = pq.read_table(out_root / "site=sample.stackexchange.com").to_pylist()
        return stats, {r["Id"]: r for r in rows}

    return _run


def test_users_drop_personal_text(run):
    stats, rows = run("Users")
    assert stats["rows"] == 5
    cols = set(rows[2])
    assert not cols & {"DisplayName", "Location", "AboutMe", "WebsiteUrl", "ProfileImageUrl"}
    assert rows[2]["has_location"] is True
    assert rows[3]["has_location"] is False
    assert rows[5]["has_location"] is False  # empty string counts as no location
    assert rows[-1]["Reputation"] == 1
    assert rows[3]["AccountId"] is None


def test_votes_counts_by_type_and_user(run):
    stats, rows = run("Votes")
    assert stats["rows"] == 6
    assert stats["count_by"] == {"1": 1, "2": 1, "3": 1, "5": 1, "8": 1, "9": 1}
    assert stats["rows_with_user"] == 2
    assert rows[5]["BountyAmount"] == 50


def test_comments_keep_length_not_text(run):
    stats, rows = run("Comments")
    assert stats["rows"] == 3
    assert "Text" not in rows[1]
    assert rows[1]["text_chars"] == len("Did you try reversed()? It's built-in & lazy.")
    assert rows[3]["text_chars"] == 0
    assert rows[2]["user_deleted"] is True
    assert rows[1]["user_deleted"] is False


def test_postlinks_and_tags(run):
    stats, rows = run("PostLinks")
    assert stats["count_by"] == {"1": 1, "3": 1}
    assert rows[1]["RelatedPostId"] == 5
    stats, rows = run("Tags")
    assert stats["rows"] == 4
    assert {r["TagName"] for r in rows.values()} == {"python", "c++", "c#", "python-3.x"}


def test_success_marker_and_skip(run, tmp_path, monkeypatch):
    run("Votes")
    marker = tmp_path / "votes" / "site=sample.stackexchange.com" / "_SUCCESS.json"
    assert json.loads(marker.read_text())["rows"] == 6
    monkeypatch.setattr(tables, "iter_rows", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    stats, _ = run("Votes")
    assert stats["rows"] == 6
