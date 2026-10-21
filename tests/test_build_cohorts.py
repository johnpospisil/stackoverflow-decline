from datetime import datetime
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from sod import config
from sod.build import cohorts
from sod.ingest import posts, tables

FIXTURE_SITE = Path(__file__).parent / "fixtures" / "sample.stackexchange.com"
SITE = FIXTURE_SITE.name


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("c")
    mp = pytest.MonkeyPatch()
    mp.setattr(config, "DATA_DIR", tmp)
    mp.setattr(config, "PARQUET_DIR", tmp / "parquet")
    for mod in (posts, tables, cohorts):
        mp.setattr(mod.progress, "PROGRESS_DIR", tmp / "progress")
    posts.ingest_site(FIXTURE_SITE, tmp / "parquet" / "posts", job="t")
    tables.ingest_table(FIXTURE_SITE, "Comments", tmp / "parquet" / "comments", job="t")
    out = tmp / "parquet"
    cohorts.build_site(SITE, out, job="t")

    def read(name):
        return pq.read_table(out / name / f"site={SITE}").to_pylist()

    yield {n: read(n) for n in cohorts.OUTPUTS}
    mp.undo()


def test_user_months_count_questions_and_answers(built):
    um = {(r["user_id"], r["month"].isoformat()): r for r in built["user_months"]}
    assert um[(2, "2010-07-01")]["n_questions"] == 1
    assert um[(2, "2022-12-01")]["n_answers"] == 1
    assert um[(3, "2010-07-01")]["n_answers"] == 1
    assert um[(3, "2010-07-01")]["n_comments"] == 1  # comment Id 1 by user 3
    assert all(r["user_id"] > 0 for r in built["user_months"])  # community user excluded


def test_user_summary_first_post_and_return(built):
    us = {r["user_id"]: r for r in built["user_summary"]}
    assert set(us) == {2, 3, 4, 5}
    assert us[2]["first_post_month"].isoformat() == "2010-07-01"
    assert us[2]["first_post_type"] == "question"
    gap = datetime(2022, 12, 1) - datetime(2010, 7, 20, 19, 18, 1, 250000)  # Q5 -> answer 13
    assert us[2]["days_to_second_post"] == pytest.approx(gap.total_seconds() / 86400, abs=1e-4)
    assert us[3]["first_post_type"] == "answer"
    assert us[4]["days_to_second_post"] is None
    assert not any(r["core_answerer"] for r in built["user_summary"])  # no 2019-21 answers


def test_cohort_activity(built):
    ca = {(r["cohort_month"].isoformat(), r["months_since"]): r for r in built["cohort_activity"]}
    assert ca[("2010-07-01", 0)]["cohort_size"] == 2  # users 2 and 3
    assert ca[("2010-07-01", 0)]["active"] == 2
    assert ca[("2010-07-01", 149)]["active"] == 1  # user 2 answers in 2022-12


def test_answer_concentration(built):
    by_year = {r["year"]: r for r in built["answer_concentration"]}
    assert by_year[2010]["answerers"] == 1
    assert by_year[2010]["top1pct_share"] == pytest.approx(1.0)
