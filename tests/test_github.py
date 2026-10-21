import pandas as pd
import pytest

from sod.models import github as g


def test_index_100_uses_2019_2021_mean():
    idx = pd.date_range("2019-01-01", "2025-12-01", freq="MS")
    s = pd.Series(10.0, index=idx)
    s[s.index.year >= 2023] = 5.0
    i = g.index_100(s)
    assert i["2020-06-01"] == pytest.approx(100)
    assert i["2024-06-01"] == pytest.approx(50)


def test_monthly_pivot_labels_baseline():
    df = pd.DataFrame(
        {
            "month": ["201901", "201901", "201901"],
            "type": ["IssuesEvent", "IssuesEvent", "IssueCommentEvent"],
            "repo_id": [858127, 0, 858127],
            "events": [5, 100, 7],
        }
    )
    m = g.monthly(df)
    pandas_row = m[m["repo_id"] == 858127].iloc[0]
    assert pandas_row["IssuesEvent"] == 5 and pandas_row["IssueCommentEvent"] == 7
    assert pandas_row["tag"] == "pandas"
    assert m.loc[m["repo_id"] == 0, "repo"].iloc[0] == "all other repositories"


def test_cache_exists_and_covers_period():
    d = pd.read_csv(g.CACHE, dtype={"month": str})
    assert d["month"].min() == "201901" and d["month"].max() == "202609"
