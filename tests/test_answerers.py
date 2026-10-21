import pandas as pd
import pytest

from sod.models import answerers as A


def _ya():
    # 200 answerers per year 2014-2025; users 0-1 answer most in every window.
    rows = []
    for y in range(2014, 2026):
        for u in range(200):
            n = 100 if u < 2 else 1
            if u == 1 and y >= 2023:
                continue  # user 1 stops answering after ChatGPT
            rows.append({"site": "x", "user_id": u, "year": y, "answers": n})
    return pd.DataFrame(rows)


def test_core_is_top_one_percent():
    assert A.core_set(_ya(), 2019, 2021) == {0, 1}


def test_cohort_table_and_h5():
    ct = A.cohort_table(_ya())
    s = ct.set_index(["window", "distance"])["share"]
    assert s[("2016-18", 3)] == 1.0  # 2021: both active
    assert s[("2019-21", 2)] == pytest.approx(0.5)  # 2023: user 1 gone
    assert ("2021-23", 3) not in s.index  # 2026 not a full year
    t = A.h5_test(ct)
    assert t["supported"] and t["distance_2"]["reference_min"] == 1.0
