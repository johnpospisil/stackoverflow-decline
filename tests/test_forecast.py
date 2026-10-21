import numpy as np
import pandas as pd
import pytest

from sod.models import forecast as f


def _series(pct_per_year=-8.0, start="2017-01-01", end="2022-11-01", seed=0):
    idx = pd.date_range(start, end, freq="MS")
    t = np.arange(len(idx)) / 12
    rng = np.random.default_rng(seed)
    log_y = 11 + np.log(1 + pct_per_year / 100) * t + 0.05 * np.sin(2 * np.pi * t)
    return pd.Series(log_y + rng.normal(0, 0.01, len(idx)), index=pd.DatetimeIndex(idx, freq="MS"))


def test_gaps_zero_when_actual_equals_paths():
    idx = pd.date_range("2023-01-01", periods=24, freq="MS")
    paths = np.log(np.full((24, 50), 1000.0))
    g = f.gaps(pd.Series(1000.0, index=idx), paths)
    assert g["all_post"]["mean_gap_pct"] == pytest.approx(0)
    assert g["2024"]["cumulative_gap_pct"] == pytest.approx(0)
    assert g["to_2025_09"]["months"] == 24


def test_gaps_detect_halving():
    idx = pd.date_range("2023-01-01", periods=12, freq="MS")
    paths = np.log(np.full((12, 50), 1000.0))
    g = f.gaps(pd.Series(500.0, index=idx), paths)
    assert g["all_post"]["mean_gap_pct"] == pytest.approx(-50)


def test_ets_recovers_trend_forecast():
    train = _series()
    res, trend, _ = f.fit_ets(train)
    paths = f.ets_paths(res, 12)
    truth = 11 + np.log(0.92) * (len(train) + 5.5) / 12  # mid of the next year
    assert np.median(paths, axis=1).mean() == pytest.approx(truth, abs=0.05)


def test_accuracy_horizon_years():
    idx = pd.date_range("2019-12-01", periods=36, freq="MS")
    paths = np.log(np.full((36, 10), 100.0))
    acc = f.accuracy(pd.Series(100.0, index=idx), paths)
    assert set(acc["mean_error_pct_by_horizon_year"]) == {"1", "2", "3"}
    assert acc["excl_covid"]["months"] == 32
