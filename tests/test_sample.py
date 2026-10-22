"""P28: the synthetic sample dump parses with the strict real-dump schema."""

from __future__ import annotations

import numpy as np
import pytest

from sod import config, sample
from sod.ingest.xml_rows import convert_row, iter_rows


@pytest.fixture(scope="module")
def site_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("raw")
    site = "cooking.stackexchange.com"
    stats = sample.make_site(site, out, np.random.default_rng(0), scale=0.2)
    assert stats["questions"] > 100
    return out / site


@pytest.mark.parametrize("table", config.XML_TABLES)
def test_sample_tables_parse(site_dir, table):
    rows = [convert_row(table, r) for r in iter_rows(site_dir / f"{table}.xml")]
    assert rows


def test_sample_answers_follow_questions(site_dir):
    posts = [convert_row("Posts", r) for r in iter_rows(site_dir / "Posts.xml")]
    q = {p["Id"]: p["CreationDate"] for p in posts if p["PostTypeId"] == 1}
    answers = [p for p in posts if p["PostTypeId"] == 2]
    assert answers and all(a["CreationDate"] >= q[a["ParentId"]] for a in answers)
    assert max(p["CreationDate"] for p in posts).date() <= config.DUMP_CUTOFF


def test_generator_refuses_real_paths(monkeypatch):
    monkeypatch.setattr(config, "SAMPLE", False)
    with pytest.raises(SystemExit):
        monkeypatch.setattr("sys.argv", ["sod.sample"])
        sample.main()
