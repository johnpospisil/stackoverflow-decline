import numpy as np
import pytest

from sod.models import responsiveness as r


def test_wilson_interval_contains_rate():
    lo, hi = r.wilson(np.array([50, 0]), np.array([100, 10]))
    assert lo[0] < 0.5 < hi[0]
    assert lo[0] == pytest.approx(0.4038, abs=1e-3) and hi[0] == pytest.approx(0.5962, abs=1e-3)
    assert lo[1] == pytest.approx(0, abs=1e-12) and 0 < hi[1] < 0.35


def test_wilson_handles_empty():
    lo, hi = r.wilson(np.array([0]), np.array([0]))
    assert np.isnan(lo[0]) and np.isnan(hi[0])
