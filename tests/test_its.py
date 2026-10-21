import numpy as np
import pandas as pd
import pytest

from sod.models import its


def test_thanksgiving_dates():
    assert its.thanksgiving(2022) == pd.Timestamp("2022-11-24")
    assert its.thanksgiving(2024) == pd.Timestamp("2024-11-28")


def test_design_dummies_and_break_terms():
    weeks = pd.date_range("2022-11-14", "2023-01-09", freq="W-MON")
    X = its.design(weeks, pd.Timestamp("2017-01-02"))
    assert X.loc["2022-11-21", "thanksgiving"] == 1
    assert X.loc["2022-12-19", "christmas"] == 1  # week of Mon 19 Dec contains 25 Dec
    assert X.loc["2022-12-26", "new_year"] == 1  # contains 1 Jan 2023
    assert X.loc["2022-11-21", "post"] == 0 and X.loc["2022-11-28", "post"] == 1
    assert X.loc["2022-11-28", "post_slope"] == 0
    assert X.loc["2022-12-05", "post_slope"] == pytest.approx(7 / 365.25)
    assert X["covid"].sum() == 0


def test_fit_recovers_level_and_slope():
    weeks = pd.date_range("2017-01-02", "2026-09-21", freq="W-MON")
    X = its.design(weeks, pd.Timestamp("2017-01-02"))
    rng = np.random.default_rng(1)
    log_y = (
        10
        - 0.08 * X["trend"]
        + 0.05 * X["sin1"]
        - 0.3 * X["christmas"]
        + np.log(0.8) * X["post"]
        - 0.5 * X["post_slope"]
        + rng.normal(0, 0.01, len(weeks))
    )
    y = pd.Series(np.exp(log_y), index=weeks)
    model, Xf, yy = its.fit(y, "2017-01-02")
    g = its.gaps(model, Xf, yy)
    assert g["post"]["pct"] == pytest.approx(-20, abs=1)
    assert model.params["post_slope"] == pytest.approx(-0.5, abs=0.02)
    # mean gap over all post weeks equals level + slope * mean(years since break)
    expected = np.log(0.8) - 0.5 * Xf.loc[Xf["post"] == 1, "post_slope"].mean()
    assert g["windows"]["all_post"]["mean_log_gap"] == pytest.approx(expected, abs=0.01)
    lo, hi = g["windows"]["all_post"]["mean_gap_pct_ci"]
    assert lo < g["windows"]["all_post"]["mean_gap_pct"] < hi
