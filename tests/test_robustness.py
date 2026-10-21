import numpy as np
import pandas as pd

from sod.models import robustness as r


def test_make_masks_monthly():
    idx = pd.date_range("2017-01-01", "2026-09-01", freq="MS")
    pre, post = r.make_masks(idx, "2022-11-01", exclude_post=r.STRIKE)
    assert pre.sum() == 67 and post.sum() == 46 - 3
    _, post7 = r.make_masks(idx, "2022-11-01", post_end="2025-09-01")
    assert idx[post7].max() == pd.Timestamp("2025-09-01")
    pre10, _ = r.make_masks(idx, "2022-11-01", exclude_pre=("2022-11-01", "2022-11-01"))
    assert pre10.sum() == 66


def test_make_masks_weekly_covid():
    idx = pd.date_range("2020-02-24", "2020-07-13", freq="W-MON")
    pre, _ = r.make_masks(idx, "2022-11-21", weekly=True)
    assert not pre[idx.get_loc(pd.Timestamp("2020-03-09"))]
    assert pre[idx.get_loc(pd.Timestamp("2020-03-02"))]
    assert pre[idx.get_loc(pd.Timestamp("2020-07-06"))]


def test_h1_holds():
    assert r.h1_holds({"att_pct": -50, "high": -20, "rank": 1})
    assert not r.h1_holds({"att_pct": -50, "high": 5, "rank": 1})
    assert not r.h1_holds({"att_pct": -50, "high": -20, "rank": 2})
    assert r.h1_holds({"att_pct": -50, "high": np.nan}) is None
