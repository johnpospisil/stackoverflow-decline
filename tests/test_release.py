"""P32: the release files contain derived counts only and match their checksums."""

from __future__ import annotations

import hashlib

import pandas as pd
import pytest

from sod import release

FORBIDDEN = ("body", "title", "text", "name", "user_id", "userid", "owner", "display", "email")


@pytest.fixture(scope="module")
def out():
    if not (release.OUT / "SHA256SUMS").exists():
        pytest.skip("run `make release` first")
    return release.OUT


def test_no_text_or_user_columns(out):
    for f in (out / "data").glob("*.parquet"):
        cols = pd.read_parquet(f).columns
        bad = [c for c in cols if any(k in c.lower() for k in FORBIDDEN)]
        assert not bad, (f.name, bad)


def test_every_column_is_documented(out):
    documented = set(release.COLUMNS) | set(release.TAG_EST_COLUMNS)
    for f in (out / "data").glob("*.parquet"):
        assert set(pd.read_parquet(f).columns) <= documented, f.name


def test_checksums_match(out):
    for line in (out / "SHA256SUMS").read_text().splitlines():
        digest, path = line.split("  ", 1)
        assert hashlib.sha256((out / path).read_bytes()).hexdigest() == digest, path


def test_card_has_licence_and_attribution(out):
    card = (out / "README.md").read_text()
    assert "license: cc-by-sa-4.0" in card
    assert "CC BY-SA 4.0" in card and "not affiliated" in card.lower()
    assert "language models" in card  # restates the dump's no-LLM-training term


def test_csv_matches_parquet(out):
    for f in (out / "data").glob("*.parquet"):
        assert len(pd.read_parquet(f)) == len(pd.read_csv(f.with_suffix(".csv"))), f.name
