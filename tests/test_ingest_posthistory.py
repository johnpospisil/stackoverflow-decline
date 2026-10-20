import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from sod.ingest import posthistory
from sod.ingest.posthistory import parse_close

FIXTURE_SITE = Path(__file__).parent / "fixtures" / "sample.stackexchange.com"


@pytest.fixture()
def ingested(tmp_path, monkeypatch):
    monkeypatch.setattr(posthistory.progress, "PROGRESS_DIR", tmp_path / "progress")
    out_root = tmp_path / "posthistory"
    stats = posthistory.ingest_site(FIXTURE_SITE, out_root, job="test")
    rows = pq.read_table(out_root / "site=sample.stackexchange.com").to_pylist()
    return stats, {r["Id"]: r for r in rows}


def test_keeps_only_event_types_of_interest(ingested):
    stats, rows = ingested
    assert set(rows) == {2, 3, 4, 5, 6, 7, 9}  # drops body rows (Ids 1 and 8)
    assert stats["rows_kept"] == 7
    assert stats["rows_read"] == 9
    assert stats["count_by_type"] == {"1": 1, "2": 1, "3": 1, "5": 1, "6": 1, "10": 3, "11": 1}


def test_no_text_kept(ingested):
    _, rows = ingested
    assert not set(rows[2]) & {"Text", "Comment", "UserDisplayName", "RevisionGUID"}


def test_duplicate_close(ingested):
    _, rows = ingested
    r = rows[5]
    assert r["PostHistoryTypeId"] == 10
    assert r["close_reason_id"] == 101
    assert r["is_duplicate"] is True
    assert r["duplicate_of"] == [5]
    assert r["n_voters"] == 1
    assert r["binding"] == "GoldTagBadge"


def test_other_close_and_old_duplicate_reason(ingested):
    _, rows = ingested
    assert rows[7]["close_reason_id"] == 103
    assert rows[7]["is_duplicate"] is False
    assert rows[7]["binding"] is None
    assert rows[9]["close_reason_id"] == 1  # old "exact duplicate"
    assert rows[9]["is_duplicate"] is True
    assert rows[9]["duplicate_of"] == []
    assert rows[9]["n_voters"] == 0


def test_reopen_and_tag_events(ingested):
    _, rows = ingested
    assert rows[6]["PostHistoryTypeId"] == 11
    assert rows[6]["n_voters"] == 1
    assert rows[6]["close_reason_id"] is None
    assert rows[3]["tags"] == ["python", "list"]
    assert rows[4]["tags"] == ["python", "list", "reverse"]
    assert rows[2]["tags"] is None  # title event: no tags


def test_marker(ingested, tmp_path):
    marker = tmp_path / "posthistory" / "site=sample.stackexchange.com" / "_SUCCESS.json"
    assert json.loads(marker.read_text())["rows_kept"] == 7


@pytest.mark.parametrize(
    ("comment", "text", "expected"),
    [
        ("102", '{"Voters":[{"Id":1},{"Id":2},{"Id":3}]}', (102, False, [], 3, None)),
        (
            "101",
            '{"OriginalQuestionIds":[7,8],"Voters":[{"Id":9,"BindingReason":"Moderator"}]}',
            (101, True, [7, 8], 1, "Moderator"),
        ),
        (
            "101",
            '{"OriginalQuestionIds":[3],"Voters":[{"Id":4,"BindingReason":'
            '{"DuplicateApprovedByAsker":""}}]}',
            (101, True, [3], 1, "DuplicateApprovedByAsker"),
        ),
        ("not-a-number", None, (None, False, [], 0, None)),
        (None, "not json", (None, False, [], 0, None)),
    ],
)
def test_parse_close(comment, text, expected):
    assert parse_close(comment, text) == expected
