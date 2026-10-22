"""P33: README links resolve and its headline numbers match the pipeline's output."""

from __future__ import annotations

import re

import pytest

from sod import article, config

README = config.REPO_ROOT / "README.md"


def test_relative_links_exist():
    text = README.read_text()
    links = re.findall(r"\]\(([^)#]+)\)", text) + re.findall(
        r'srcset="([^"]+)"|src="([^"]+)"', text
    )
    paths = [p for group in links for p in (group if isinstance(group, tuple) else (group,)) if p]
    local = [p for p in paths if not p.startswith(("http://", "https://"))]
    assert local
    missing = [p for p in local if not (config.REPO_ROOT / p).exists()]
    assert not missing, missing


def test_headline_numbers_match():
    if not (config.REPORT_DIR / "qa" / "validation_summary.json").exists() or config.SAMPLE:
        pytest.skip("needs the real model summaries")
    article.numbers.cache_clear()
    n = article.numbers()
    text = README.read_text().replace("−", "-")
    for key in ("att", "att_2023", "att_2026", "new_tags_gap", "top300_gap", "donor_gap"):
        assert n[key].replace("−", "-") in text, (key, n[key])
    assert n["att_ci"].replace("−", "-") in text
    assert n["missing"] in text
    assert f"{n['n_tags']} of the largest tags" in text
