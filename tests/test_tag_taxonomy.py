import pandas as pd

from sod import config

FAMILIES = {
    "language",
    "web",
    "framework",
    "mobile",
    "data_ml",
    "database",
    "cloud",
    "devops",
    "tooling",
    "office",
    "concept",
}


def test_tag_families_complete():
    f = pd.read_csv(config.REFERENCE_DIR / "tag_families.csv")
    assert len(f) == 300
    assert f["tag"].is_unique
    assert set(f["family"]) <= FAMILIES
    assert sorted(f["rank_2019_2021"]) == list(range(1, 301))


def test_tag_features_use_pre_period_and_are_sane():
    f = pd.read_csv(config.REFERENCE_DIR / "tag_features.csv", parse_dates=["first_seen"])
    assert len(f) == 300
    assert (f["first_seen"] < pd.Timestamp(config.BREAK_DATE)).all()
    assert f["dup_share_2019_2021"].between(0, 1).all()
    assert (f["stock_to_2021_09"] >= f["size_2019_2021"] * 0.5).all()
    assert (f["age_years_at_break"] > 0).all()


def test_new_tags_classified():
    n = pd.read_csv(config.REFERENCE_DIR / "tags_new_post2021.csv", parse_dates=["first_seen"])
    assert (n["first_seen"] >= pd.Timestamp("2021-10-01")).all()
    assert (n["n_questions"] >= 200).all()
    assert "new" in set(n["kind"]) and set(n["kind"]) <= {"version", "feature", "new"}
