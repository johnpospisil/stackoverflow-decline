from pathlib import Path

import pandas as pd
import pytest

from sod import config
from sod.build import cohorts, panels, questions
from sod.ingest import posthistory, posts, tables

FIXTURE_SITE = Path(__file__).parent / "fixtures" / "sample.stackexchange.com"
SITE = FIXTURE_SITE.name


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("p")
    mp = pytest.MonkeyPatch()
    mp.setattr(config, "DATA_DIR", tmp)
    mp.setattr(config, "PARQUET_DIR", tmp / "parquet")
    for mod in (posts, tables, posthistory, questions, cohorts, panels):
        mp.setattr(mod.progress, "PROGRESS_DIR", tmp / "progress")
    pqd = tmp / "parquet"
    posts.ingest_site(FIXTURE_SITE, pqd / "posts", job="t")
    for t in ("Users", "Votes", "Comments"):
        tables.ingest_table(FIXTURE_SITE, t, pqd / t.lower(), job="t")
    posthistory.ingest_site(FIXTURE_SITE, pqd / "posthistory", job="t")
    questions.build_site(SITE, pqd / "questions", job="t")
    cohorts.build_site(SITE, pqd, job="t")
    out = panels.build(tmp / "panels", job="t", with_sede=False)
    yield out
    mp.undo()


def test_site_week_counts(built):
    w = built["site_week"].set_index("period")
    wk = w.loc[pd.Timestamp("2010-07-19")]
    assert wk["questions"] == 2  # Q5 and Q7
    assert wk["answers"] == 1  # A9
    assert wk["new_posters"] == 2  # users 2 and 3 (Q7's owner is deleted)
    assert wk["eligible_24h"] == 2
    assert wk["answered_24h"] == 1  # Q5 answered in 7 minutes; Q7 years later
    assert wk["accepted_30d"] == 1  # Q5's answer accepted next day
    assert wk["closed_duplicate"] == 1  # Q7


def test_fixed_windows_exclude_questions_too_close_to_cutoff(built):
    w = built["site_week"].set_index("period")
    last = w.loc[pd.Timestamp("2026-09-28")]  # Q20 on 2026-09-30
    assert last["questions"] == 1
    assert last["eligible_24h"] == 0
    assert last["eligible_30d"] == 0
    assert bool(last["partial_period"]) and bool(last["final_8_weeks"])


def test_site_month_and_tags(built):
    m = built["site_month"].set_index("period")
    assert m.loc[pd.Timestamp("2010-07-01"), "questions"] == 2
    # fixture tags are not in the top-300/new tag lists, so the tag panel is empty
    assert built["tag_week"].empty
