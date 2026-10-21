import numpy as np
import pytest

from sod.models import newcomers as nc


def test_km_without_censoring_is_empirical_share():
    d = np.array([10.0, 50.0, 100.0, 400.0, 500.0])
    e = np.ones(5, bool)
    r = nc.km_at(d, e, times=(91, 365))
    assert r[91]["p"] == pytest.approx(0.4)
    assert r[365]["p"] == pytest.approx(0.6)
    assert r["n"] == 5


def test_km_handles_censoring():
    # 4 users: event at 10; censored at 20; event at 30; censored at 40
    d = np.array([10.0, 20.0, 30.0, 40.0])
    e = np.array([1, 0, 1, 0], bool)
    r = nc.km_at(d, e, times=(35,))
    # S = (1 - 1/4) * (1 - 1/2) = 0.375
    assert r[35]["p"] == pytest.approx(1 - 0.375)
    assert r[35]["se"] > 0


def test_km_before_first_event():
    r = nc.km_at(np.array([100.0, 200.0]), np.array([1, 1], bool), times=(50,))
    assert r[50]["p"] == 0 and r[50]["se"] == 0
