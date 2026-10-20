import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from sod.ingest import posts

FIXTURE_SITE = Path(__file__).parent / "fixtures" / "sample.stackexchange.com"


@pytest.fixture()
def ingested(tmp_path, monkeypatch):
    monkeypatch.setattr(posts.progress, "PROGRESS_DIR", tmp_path / "progress")
    out_root = tmp_path / "posts"
    stats = posts.ingest_site(FIXTURE_SITE, out_root, job="test")
    table = pq.read_table(out_root / "site=sample.stackexchange.com").to_pylist()
    return stats, {r["Id"]: r for r in table}, out_root


def test_watermark_rows_excluded_and_logged(ingested):
    stats, rows, _ = ingested
    assert 1000000001 not in rows
    assert stats["watermark_ids_excluded"] == [1000000001]
    assert len(rows) == 9


def test_no_raw_text_or_names_stored(ingested):
    _, rows, _ = ingested
    cols = set(next(iter(rows.values())))
    assert not cols & {"Body", "Title", "OwnerDisplayName", "LastEditorDisplayName"}
    assert {"text_chars", "n_code_blocks", "title_chars", "tags", "n_tags"} <= cols


def test_values_and_features(ingested):
    _, rows, _ = ingested
    q = rows[5]
    assert q["PostTypeId"] == 1
    assert q["tags"] == ["python", "list"]
    assert q["n_tags"] == 2
    assert q["n_code_blocks"] == 1
    assert q["n_inline_code"] == 2
    assert rows[7]["tags"] == ["performance", "c++", "c#"]
    assert rows[7]["OwnerUserId"] is None
    assert rows[7]["owner_deleted"] is True
    assert rows[5]["owner_deleted"] is False
    assert rows[20]["ViewCount"] == 2_147_483_648
    assert rows[9]["tags"] == []


def test_stats_and_success_marker(ingested):
    stats, _, out_root = ingested
    marker = out_root / "site=sample.stackexchange.com" / "_SUCCESS.json"
    assert json.loads(marker.read_text())["rows"] == 9
    assert stats["rows_by_type"] == {"1": 4, "2": 2, "4": 1, "5": 1, "7": 1}
    assert stats["duplicate_ids"] == 0
    assert stats["max_question_date"] == "2026-09-30T08:36:56.830000"
    assert stats["owner_minus1_qa_ids"] == []


def test_skips_site_already_done(ingested, monkeypatch):
    _, _, out_root = ingested

    def boom(*a, **k):
        raise AssertionError("should not re-parse a finished site")

    monkeypatch.setattr(posts, "iter_rows", boom)
    stats = posts.ingest_site(FIXTURE_SITE, out_root, job="test")
    assert stats["rows"] == 9
