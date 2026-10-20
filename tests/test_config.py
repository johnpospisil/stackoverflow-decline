from sod import config


def test_site_groups_have_no_duplicates():
    assert len(config.ALL_SITES) == len(set(config.ALL_SITES)) == 27


def test_site_group_lookup():
    assert config.site_group("stackoverflow.com") == "treated"
    assert config.site_group("cooking.stackexchange.com") == "donor"


def test_break_week_is_monday_of_release_week():
    assert config.BREAK_WEEK.weekday() == 0
    assert 0 <= (config.BREAK_DATE - config.BREAK_WEEK).days < 7


def test_env_overrides_paths(monkeypatch, tmp_path):
    import importlib

    monkeypatch.setenv("SOD_RAW_DIR", str(tmp_path / "raw"))
    monkeypatch.setenv("SOD_DATA_DIR", str(tmp_path / "out"))
    reloaded = importlib.reload(config)
    try:
        assert reloaded.RAW_DIR == tmp_path / "raw"
        assert reloaded.PARQUET_DIR == tmp_path / "out" / "parquet"
    finally:
        monkeypatch.undo()
        importlib.reload(config)
