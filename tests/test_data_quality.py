"""Checks on the latest data-quality profile (report/qa/quality.json, from `python -m
sod.build.quality`). Thresholds are set from the P08 run; a regression fails here."""

import json
from pathlib import Path

import pytest

QA = Path(__file__).parents[1] / "report" / "qa" / "quality.json"


@pytest.fixture(scope="module")
def qa() -> dict:
    if not QA.exists():
        pytest.skip("run `python -m sod.build.quality` first")
    return json.loads(QA.read_text())


@pytest.mark.parametrize(
    "check",
    [
        "duplicate_post_ids",
        "orphan_answers",
        "posts_outside_date_range",
        "questions_without_tags",
        "orphan_comments",
        "duplicate_user_ids",
        "question_owner_not_in_users",
    ],
)
def test_checks_that_must_be_zero(qa, check):
    assert qa["totals"][check] == 0, qa["checks"][check]


def test_near_zero_checks(qa):
    t = qa["totals"]
    assert t["accepted_answer_missing"] <= 100
    assert t["orphan_posthistory"] <= 10
    # merged questions can leave answers older than their (new) question
    assert t["answer_before_question"] <= 5_000


def test_initial_tags_coverage(qa):
    so_missing = qa["checks"]["questions_without_initial_tags_event"]["stackoverflow.com"]
    assert so_missing <= 0.0001 * 24_133_975


def test_tag_counts_match_tags_xml(qa):
    assert qa["tags_xml_vs_computed"]["max_abs_pct_diff"] <= 0.1


def test_no_unexplained_zero_weeks_on_treated_or_donors(qa):
    import pandas as pd

    from sod import config

    a = pd.read_csv(QA.parent / "weekly_anomalies.csv")
    zero = a[(a["questions"] == 0) & (a["kind"] == "other")]
    watched = {config.TREATED, "math.stackexchange.com", "physics.stackexchange.com"}
    assert zero[zero["site"].isin(watched)].empty
