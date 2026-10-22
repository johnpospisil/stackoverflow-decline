"""P30: every number the article quotes exists and is well formed."""

from __future__ import annotations

import re

import pytest

from sod import article, config

QMD = config.REPO_ROOT / "report" / "index.qmd"


@pytest.fixture(scope="module")
def nums():
    if not (config.REPORT_DIR / "qa" / "validation_summary.json").exists():
        pytest.skip("model summaries not built")
    article.numbers.cache_clear()
    return article.numbers()


def test_every_key_used_in_article_exists(nums):
    used = set(re.findall(r'N\["([a-z0-9_]+)"\]', QMD.read_text()))
    assert used, "article uses no numbers?"
    assert used <= set(nums), sorted(used - set(nums))


def test_numbers_are_well_formed(nums):
    for k, v in nums.items():
        assert v and "nan" not in v.lower() and "None" not in v, (k, v)
        if not config.SAMPLE:  # the synthetic sample can give an empty interval
            assert "n/a" not in v, (k, v)


def test_formatting():
    assert article.pct(-72.31) == "−72%"
    assert article.pct(18.3) == "+18%"
    assert article.pct(-72.31, sign=False) == "72%"
    assert article.share(0.4398, 1) == "44.0%"
    assert article.millions(1_574_501) == "1.6 million"
