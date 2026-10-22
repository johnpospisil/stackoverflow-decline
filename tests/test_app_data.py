"""P31: the tag lookup app's precomputed data (app/data/tags.json) is complete and consistent."""

from __future__ import annotations

import json

import pytest

from sod import config

APP = config.REPO_ROOT / "app"
DATA = APP / "data" / "tags.json"


@pytest.fixture(scope="module")
def data():
    if not DATA.exists():
        pytest.skip("run `python -m sod.app_data` first")
    return json.loads(DATA.read_text())


def test_top_tags_ranked_once(data):
    top = [t for t in data["tags"] if t["kind"] == "top"]
    assert len(top) == data["n_ranked"] == 297
    assert sorted(t["rank"] for t in top) == list(range(1, 298))
    by_rank = sorted(top, key=lambda t: t["rank"])
    assert all(
        a["pct"] <= b["pct"] for a, b in zip(by_rank, by_rank[1:], strict=False)
    )  # 1 = fell most


def test_top_tags_have_series_and_counterfactual(data):
    for t in (t for t in data["tags"] if t["kind"] == "top"):
        assert t["lo"] <= t["pct"] <= t["hi"], t["tag"]
        assert t["w"] and min(t["w"]) >= 0
        assert len(t["cf"]) == len(t["cl"]) == len(t["ch"]) > 0
        assert all(lo <= m <= hi for lo, m, hi in zip(t["cl"], t["cf"], t["ch"], strict=True)), t[
            "tag"
        ]


def test_new_tags_have_no_trend_line(data):
    new = [t for t in data["tags"] if t["kind"] == "new"]
    assert 50 <= len(new) <= 69
    assert all("cf" not in t and t["w"] for t in new)


def test_tags_unique_and_published_page_points_at_data(data):
    names = [t["tag"] for t in data["tags"]]
    assert len(names) == len(set(names))
    html = (APP / "index.html").read_text()
    assert 'fetch("data/tags.json")' in html and "CC BY-SA 4.0" in html


def test_bundle_is_small():
    size = sum(p.stat().st_size for p in APP.rglob("*") if p.is_file())
    assert size < 3_000_000
