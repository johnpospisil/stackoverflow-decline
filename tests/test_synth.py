import numpy as np
import pandas as pd
import pytest

from sod.models import synth as s


def _panel(effect=-1.0, seed=0):
    idx = pd.date_range("2017-01-01", "2026-09-01", freq="MS")
    rng = np.random.default_rng(seed)
    donors = pd.DataFrame(
        rng.normal(0, 0.02, (len(idx), 4)).cumsum(axis=0), index=idx, columns=list("abcd")
    )
    w = np.array([0.5, 0.3, 0.2, 0.0])
    D = donors.copy()
    D["t"] = donors.to_numpy() @ w + rng.normal(0, 0.01, len(idx))
    pre, post = s.masks(idx)
    D.loc[post, "t"] += effect
    return D, pre, post, w


def test_simplex_weights_recover_mix():
    D, pre, post, w = _panel()
    r = s.synth(D, "t", list("abcd"), pre, post)
    got = np.array([r["weights"][k] for k in "abcd"])
    assert got.sum() == pytest.approx(1)
    assert (got >= 0).all()
    assert got == pytest.approx(w, abs=0.05)
    assert r["att_log"] == pytest.approx(-1.0, abs=0.05)


def test_masks_exclude_covid_and_split_at_break():
    idx = pd.date_range("2017-01-01", "2026-09-01", freq="MS")
    pre, post = s.masks(idx)
    assert pre.sum() == 71 - 4 and post.sum() == 46
    assert not pre[idx.get_loc(pd.Timestamp("2020-04-01"))]


def test_cwz_rejects_zero_for_constant_effect():
    D, pre, post, _ = _panel(effect=-1.0)
    assert s.cwz_pvalue(D, "t", list("abcd"), pre, post, 0.0) < 0.05
    assert s.cwz_pvalue(D, "t", list("abcd"), pre, post, -1.0) > 0.05


def test_monthly_its_gap_zero_without_break():
    idx = pd.date_range("2017-01-01", "2026-09-01", freq="MS")
    t = (idx - idx[0]).days / 365.25
    y = pd.Series(10 - 0.1 * t + 0.05 * np.sin(2 * np.pi * idx.month / 12), index=idx)
    assert s.monthly_its_gap(y) == pytest.approx(0, abs=1e-6)
