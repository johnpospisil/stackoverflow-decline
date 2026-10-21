import numpy as np
import pandas as pd
import pytest

from sod.models import question_mix as qm


def test_weighted_median_and_mean():
    x = np.array([1.0, 2.0, 3.0, np.nan])
    w = np.array([1.0, 1.0, 10.0, 5.0])
    assert qm.wstat(x, w, "median") == 3.0
    assert qm.wstat(x, np.ones(4), "median") == 2.0
    assert qm.wstat(x, np.ones(4), "mean") == pytest.approx(2.0)


def test_reweight_restores_2021_tag_shares():
    # 2021: half "a", half "b"; 2025: 90% "a". Reweighted 2025 must be 50/50.
    df = pd.DataFrame(
        {
            "year": [2021] * 10 + [2025] * 10,
            "tags": [["a"]] * 5 + [["b"]] * 5 + [["a"]] * 9 + [["b"]],
            "n_tags": 1,
        }
    )
    qidx, code, frac, names = qm.explode_tags(df, {"a", "b"})
    w = qm.reweight(df["year"].to_numpy(), qidx, code, frac, np.ones(len(df)))
    w25 = w[10:]
    share_a = w25[:9].sum() / w25.sum()
    assert share_a == pytest.approx(0.5)
    assert (w[:10] == 1).all()


def test_within_and_composition_add_up():
    df = pd.DataFrame(
        {
            "year": [2021] * 4 + [2025] * 4,
            "tags": [["a"], ["a"], ["b"], ["b"], ["a"], ["a"], ["a"], ["b"]],
            "n_tags": 1,
        }
    )
    for col in (
        "body_chars",
        "code",
        "dup30",
        "first_time",
        "text_chars",
        "title_chars",
        "closed30",
        "answered7d",
        "pos_score",
        "asker_account_age_days",
    ):
        df[col] = [1.0, 1.0, 0.0, 0.0, 1.0, 1.0, 1.0, 0.0]
    qidx, code, frac, _ = qm.explode_tags(df, {"a", "b"})
    r = qm.compute(df, qidx, code, frac, np.ones(len(df)))["code_share"]
    assert r["within"] + r["composition"] == pytest.approx(r["total"])
    assert r["within"] == pytest.approx(0.0)  # within-tag values unchanged; mix shifted to "a"


def test_lee_bounds_bracket_untrimmed():
    x = np.arange(100, dtype=float)
    lo, hi = qm.lee_bounds_2021(x, "median", 0.2)
    assert lo < np.median(x) < hi
