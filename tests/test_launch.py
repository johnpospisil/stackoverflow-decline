"""P34: launch drafts fit platform limits and quote the pipeline's numbers."""

from __future__ import annotations

import re

import pytest

from sod import article, config

LAUNCH = config.REPO_ROOT / "docs" / "launch"


def test_bluesky_posts_fit():
    text = (LAUNCH / "linkedin-bluesky.md").read_text().split("## Bluesky thread")[1]
    posts = re.findall(r"^\d/ .+$", text, flags=re.M)
    assert len(posts) == 6
    for p in posts:
        assert len(p) <= 300, (len(p), p[:40])


def test_hacker_news_titles_fit():
    titles = re.findall(
        r"^\d\. \*?\*?(.+?)\*?\*?(?: \(|$)", (LAUNCH / "hacker-news.md").read_text(), flags=re.M
    )
    assert titles and all(len(t.strip("*")) <= 80 for t in titles), titles


def test_drafts_quote_current_numbers():
    if config.SAMPLE or not (config.REPORT_DIR / "qa" / "validation_summary.json").exists():
        pytest.skip("needs the real model summaries")
    article.numbers.cache_clear()
    n = {k: v.replace("−", "-") for k, v in article.numbers().items()}
    for name in ("hacker-news.md", "meta-stack-overflow.md", "linkedin-bluesky.md"):
        text = (LAUNCH / name).read_text().replace("−", "-")
        assert n["att_abs"] in text and n["att_2026"] in text, name
    hn = (LAUNCH / "hacker-news.md").read_text().replace("−", "-")
    for key in ("att_ci", "att_2023", "missing", "missing_deleted", "donor_gap"):
        assert n[key] in hn, (key, n[key])
