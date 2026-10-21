import numpy as np
import pandas as pd
import pytest

from sod import eda


def _months(site, group, pct_per_year, start="2015-01-01", end="2026-09-01", level=1000):
    period = pd.date_range(start, end, freq="MS")
    years = (period - eda.PRE_START).days / 365.25
    q = level * (1 + pct_per_year / 100) ** years
    return pd.DataFrame({"site": site, "group": group, "period": period, "questions": q})


def test_pre_slope_recovers_trend():
    g = _months("a", "donor", -10)
    r = eda.pre_slope(g)
    assert r["pct_per_year"] == pytest.approx(-10, abs=0.01)
    assert r["n_months"] == 71 - 4  # 2017-01..2022-11 minus 4 COVID months


def test_indexed_base_year_is_100():
    m = pd.concat([_months("a", "donor", -10), _months("b", "donor", 5, level=50)])
    ix = eda.indexed(m)
    base = ix[ix["period"].dt.year == 2019].groupby("site")["index"].mean()
    assert base.to_numpy() == pytest.approx([100, 100])


def test_month_profile_finds_seasonal_bump():
    g = _months("a", "donor", 0)
    g.loc[g["period"].dt.month == 3, "questions"] *= 1.2
    p = eda.month_profile(g).set_index("month")["pct"]
    assert p.idxmax() == 3
    assert p[3] > 15 and abs(p[7]) < 3


def test_holiday_ratio():
    period = pd.date_range("2016-11-07", "2018-02-26", freq="W-MON")
    q = pd.Series(100.0, index=period)
    q[pd.Timestamp("2017-12-25")] = 50  # Monday 25 Dec 2017 starts the Christmas week
    w = pd.DataFrame({"site": "a", "group": "donor", "period": period, "questions": q.to_numpy()})
    r = eda.holiday_ratios(w, years=[2017]).iloc[0]
    assert r["christmas"] == pytest.approx(0.5)
    assert r["new_year"] == pytest.approx(1.0)


def test_tracking_zero_gap_when_identical(monkeypatch):
    monkeypatch.setattr(eda.config, "site_group", lambda s: "donor" if s != "so" else "treated")
    monkeypatch.setattr(eda.config, "TREATED", "so")
    m = pd.concat([_months("so", "treated", -8), _months("d1", "donor", -8, level=10)])
    t = eda.tracking(m)
    assert t["equal_weight_rmspe_log"] == pytest.approx(0, abs=1e-9)
    assert np.isfinite(t["gap_end_log"])
