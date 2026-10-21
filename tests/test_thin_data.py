import numpy as np
import pandas as pd
import pytest

from sod.models import tags as T
from sod.models import thin_data as td


def _refs(n=20, k=60, seed=0):
    rng = np.random.default_rng(seed)
    base = 40 * np.exp(0.02 * np.arange(k))  # common lifecycle: steady growth
    R = np.round(base * rng.lognormal(0, 0.05, (n, k)))
    return pd.DataFrame(R, index=[f"r{i}" for i in range(n)], columns=range(k))


def test_lifecycle_gap_zero_when_tag_follows_benchmark():
    refs = _refs()
    y = 40 * np.exp(0.02 * np.arange(30))
    r = td.lifecycle_gap(y, refs)
    assert r["gap_pct"] == pytest.approx(0, abs=3)
    assert r["n_refs"] == 20 and r["match_factor"] == 2


def test_lifecycle_gap_detects_halving():
    refs = _refs()
    y = 40 * np.exp(0.02 * np.arange(30))
    y[4:] *= 0.5
    assert td.lifecycle_gap(y, refs)["gap_pct"] == pytest.approx(-50, abs=3)


def test_lifecycle_needs_similar_early_size():
    refs = _refs()
    y = 400 * np.exp(0.02 * np.arange(30))  # 10x the references' anchor: no match
    assert np.isnan(td.lifecycle_gap(y, refs)["gap_log"])


def test_retired_rule():
    idx = pd.date_range("2020-01-01", periods=24, freq="MS")
    q = pd.Series([100.0] * 12 + [1.0] * 12, index=idx)
    assert T.retired(q) == pd.Timestamp("2021-01-01")
    gradual = pd.Series(100 * 0.7 ** np.arange(24), index=idx)
    assert T.retired(gradual) is None
