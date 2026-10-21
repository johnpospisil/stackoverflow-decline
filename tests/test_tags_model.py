import numpy as np
import pandas as pd
import pytest

from sod.models import tags as T


def _features():
    return pd.DataFrame(
        {
            "tag": ["a", "b"],
            "family": ["language", "web"],
            "first_seen": pd.to_datetime(["2010-01-01", "2018-03-15"]),
            "age_years_at_break": [12.9, 4.7],
            "size_2019_2021": [50000, 3000],
            "dup_share_2019_2021": [0.05, 0.02],
        }
    )


def _panel(features, effect=-0.6931471805599453):  # log(0.5)
    idx = pd.date_range("2017-01-01", "2026-09-01", freq="MS")
    rows = []
    for tag in features["tag"]:
        mu = 200 * np.exp(-0.05 * (idx - idx[0]).days / 365.25)
        mu = np.where(idx > T.PRE_END, mu * np.exp(effect), mu)
        rows.append(
            pd.DataFrame(
                {
                    "period": idx,
                    "tag": tag,
                    "tag_group": "top300",
                    "partial_period": False,
                    "questions": np.round(mu),
                }
            )
        )
    return pd.concat(rows)


def test_panel_prep(monkeypatch):
    f = _features()
    monkeypatch.setattr(T, "load_features", lambda: f)
    monkeypatch.setattr(pd, "read_parquet", lambda *_a, **_k: _panel(f))
    p = T.load_panel(f)
    b = p[p["tag"] == "b"]
    assert b["period"].min() == pd.Timestamp("2018-09-01")  # first month + 6
    post = p[p["post"] == 1]
    assert post["post_slope"].groupby(post["period"]).first().mean() == pytest.approx(0, abs=1e-9)
    assert p["covid"].sum() == 8  # 4 months x 2 tags
    assert set(p["month"]) == set(range(12))


def test_unpooled_recovers_halving(monkeypatch):
    f = _features()
    monkeypatch.setattr(pd, "read_parquet", lambda *_a, **_k: _panel(f))
    raw = T.unpooled(T.load_panel(f))
    assert np.exp(raw["raw_delta"]).to_numpy() == pytest.approx([0.5, 0.5], abs=0.02)


def test_offsets_are_log_pre_means(monkeypatch):
    f = _features()
    monkeypatch.setattr(pd, "read_parquet", lambda *_a, **_k: _panel(f))
    p = T.load_panel(f)
    off = T.offsets(p, 2)
    pre = p[(p["post"] == 0) & (p["covid"] == 0) & (p["tag"] == "a")]["questions"].mean()
    assert off[0] == pytest.approx(np.log(pre))
