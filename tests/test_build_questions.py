from datetime import datetime
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from sod import config
from sod.build import questions
from sod.ingest import posthistory, posts, tables

FIXTURE_SITE = Path(__file__).parent / "fixtures" / "sample.stackexchange.com"
SITE = FIXTURE_SITE.name


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("q")
    mp = pytest.MonkeyPatch()
    mp.setattr(config, "DATA_DIR", tmp)
    mp.setattr(config, "PARQUET_DIR", tmp / "parquet")
    mp.setattr(questions.progress, "PROGRESS_DIR", tmp / "progress")
    for mod in (posts, tables, posthistory):
        mp.setattr(mod.progress, "PROGRESS_DIR", tmp / "progress")
    posts.ingest_site(FIXTURE_SITE, tmp / "parquet" / "posts", job="t")
    tables.ingest_table(FIXTURE_SITE, "Users", tmp / "parquet" / "users", job="t")
    posthistory.ingest_site(FIXTURE_SITE, tmp / "parquet" / "posthistory", job="t")
    questions.build_site(SITE, tmp / "parquet" / "questions", job="t")
    rows = pq.read_table(tmp / "parquet" / "questions" / f"site={SITE}").to_pylist()
    yield {r["Id"]: r for r in rows}
    mp.undo()


def test_one_row_per_question_and_watermark_absent(built):
    assert set(built) == {5, 7, 12, 20}


def test_week_and_month(built):
    q = built[12]  # 2022-11-30 23:59:59.999, a Wednesday
    assert q["week"].isoformat() == "2022-11-28"
    assert q["month"].isoformat() == "2022-11-01"


def test_tags_at_time_of_asking_with_fallback(built):
    assert built[5]["tags"] == ["python", "list"]  # initial-tags event
    assert built[5]["tags_source"] == "initial"
    assert built[7]["tags"] == ["performance", "c++", "c#"]  # no event: current tags
    assert built[7]["tags_source"] == "current"


def test_answers_and_acceptance(built):
    q = built[5]
    assert q["has_accepted_answer"] is True
    assert q["n_answers"] == 1
    assert q["hours_to_first_answer"] == pytest.approx((25 * 60 - 18 * 60 - 1.25) / 3600, abs=1e-3)
    assert built[12]["hours_to_first_answer"] is None
    assert built[12]["n_answers"] == 0


def test_closures(built):
    assert built[7]["ever_closed"] is True
    assert built[7]["first_close_reason"] == 101
    assert built[7]["closed_as_duplicate"] is True
    assert built[12]["first_close_reason"] == 103
    assert built[12]["closed_as_duplicate"] is False
    assert built[20]["closed_as_duplicate"] is True  # old "exact duplicate" reason 1
    assert built[5]["ever_closed"] is False


def test_asker_fields(built):
    assert built[7]["asker_account_age_days"] is None  # deleted owner
    assert built[12]["asker_account_age_days"] == pytest.approx(
        (datetime(2022, 11, 30, 23, 59, 59, 999000) - datetime(2022, 11, 30, 22)).total_seconds()
        / 86400,
        abs=1e-4,
    )
    assert built[12]["asker_first_post"] is True
    assert built[5]["asker_first_post"] is True  # user 2's answer (Id 13) came later
    assert built[7]["asker_first_post"] is None


def test_body_features_carried(built):
    assert built[5]["n_code_blocks"] == 1
    assert built[5]["has_code"] is True
    assert built[12]["has_code"] is False
