import json
from datetime import datetime
from pathlib import Path

import pytest

from sod import config
from sod.ingest import xml_rows
from sod.ingest.xml_rows import UnknownColumnError, convert_row, iter_rows, parse_tags

FIXTURES = Path(__file__).parent / "fixtures" / "sample.stackexchange.com"


def rows(table: str) -> list[dict]:
    return [convert_row(table, raw) for raw in iter_rows(FIXTURES / f"{table}.xml")]


def by_id(table: str) -> dict[int, dict]:
    return {r["Id"]: r for r in rows(table)}


# --- streaming parser -------------------------------------------------------


def test_reads_every_row_in_file_order_despite_bom():
    ids = [r["Id"] for r in rows("Posts")]
    assert ids == [5, 9, 7, 12, 13, 3, 4, 20, 8, 1000000001]


def test_raw_rows_are_plain_string_dicts():
    raw = next(iter_rows(FIXTURES / "Posts.xml"))
    assert isinstance(raw, dict)
    assert raw["Id"] == "5"
    assert all(isinstance(v, str) for v in raw.values())


@pytest.mark.parametrize(
    ("table", "n"),
    [
        ("Posts", 10),
        ("Users", 5),
        ("Votes", 6),
        ("Comments", 3),
        ("PostHistory", 9),
        ("PostLinks", 2),
        ("Tags", 4),
        ("Badges", 2),
    ],
)
def test_every_table_parses(table, n):
    assert len(rows(table)) == n


def test_columns_option_limits_returned_attributes():
    raw = next(iter_rows(FIXTURES / "Posts.xml", columns=("Id", "Tags", "NotAColumn")))
    assert raw == {"Id": "5", "Tags": "|python|list|"}


# --- type conversion ---------------------------------------------------------


def test_missing_attributes_become_none():
    post = by_id("Posts")[7]
    assert post["OwnerUserId"] is None
    assert post["OwnerDisplayName"] == "deleted-user-42"
    assert post["AcceptedAnswerId"] is None
    assert post["ParentId"] is None


def test_every_schema_column_present_in_converted_row():
    post = by_id("Posts")[9]
    assert set(post) == set(xml_rows.SCHEMAS["Posts"])


def test_integers_and_negative_and_large_values():
    posts = by_id("Posts")
    assert posts[7]["Score"] == -3
    assert posts[20]["ViewCount"] == 2_147_483_648  # beyond int32
    assert posts[3]["OwnerUserId"] == -1


def test_datetimes_parse_with_milliseconds():
    posts = by_id("Posts")
    assert posts[12]["CreationDate"] == datetime(2022, 11, 30, 23, 59, 59, 999000)
    assert posts[9]["CreationDate"] == datetime(2010, 7, 20, 19, 25, 0)
    assert posts[7]["ClosedDate"] == datetime(2010, 7, 22, 10, 0, 0)


def test_datetime_without_milliseconds():
    assert xml_rows.parse_datetime("2010-07-20T19:25:00") == datetime(2010, 7, 20, 19, 25, 0)


def test_booleans():
    tags = {t["TagName"]: t for t in rows("Tags")}
    assert tags["c#"]["IsModeratorOnly"] is True
    assert tags["c#"]["IsRequired"] is False
    assert tags["python"]["IsModeratorOnly"] is None
    badges = by_id("Badges")
    assert badges[2]["TagBased"] is True


def test_xml_entities_and_unicode_are_decoded():
    posts = by_id("Posts")
    assert posts[7]["Title"] == 'Why is "my" code <slow> & broken?'
    assert "\U0001f600" in posts[7]["Body"]
    assert "日本語" in posts[7]["Body"]
    users = by_id("Users")
    assert users[2]["DisplayName"] == "Zoë Ünicode 李"
    assert users[5]["DisplayName"] == '"quoted" & escaped'
    assert users[5]["Location"] == ""


def test_carriage_return_entities_are_kept():
    comments = by_id("Comments")
    assert comments[2]["Text"] == "Multi-line\r\ncomment with emoji \U0001f680"


def test_body_html_is_unescaped_once():
    body = by_id("Posts")[5]["Body"]
    assert body.startswith("<p>How do I reverse a list in Python?</p>")
    assert '<pre class="lang-py s-code-block"><code>' in body


def test_posthistory_json_payload_survives():
    close = by_id("PostHistory")[5]
    assert close["Comment"] == "101"
    payload = json.loads(close["Text"])
    assert payload["OriginalQuestionIds"] == [5]
    assert payload["Voters"][0]["BindingReason"] == "GoldTagBadge"


def test_unknown_attribute_raises_in_strict_mode():
    raw = {"Id": "1", "PostTypeId": "1", "BrandNewColumn": "x"}
    with pytest.raises(UnknownColumnError, match="BrandNewColumn"):
        convert_row("Posts", raw)
    assert convert_row("Posts", raw, strict=False)["Id"] == 1


def test_schemas_cover_all_tables():
    assert set(xml_rows.SCHEMAS) == set(config.XML_TABLES)


# --- tags --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("|python|list|", ["python", "list"]),
        ("<performance><c++><c#>", ["performance", "c++", "c#"]),
        ("|single-tag|", ["single-tag"]),
        ("", []),
        (None, []),
    ],
)
def test_parse_tags_both_formats(raw, expected):
    assert parse_tags(raw) == expected


def test_parse_tags_on_fixture_rows():
    posts = by_id("Posts")
    assert parse_tags(posts[20]["Tags"]) == [
        "python",
        "pandas",
        "data-frame",
        "time-series",
        "python-3.x",
    ]
    assert parse_tags(posts[7]["Tags"]) == ["performance", "c++", "c#"]


# --- real data (skipped when the drive is not mounted) -----------------------

REAL_SITES = ("cooking.stackexchange.com", config.TREATED)


@pytest.mark.data
@pytest.mark.parametrize("site", REAL_SITES)
@pytest.mark.parametrize("table", config.XML_TABLES)
def test_real_files_have_no_unknown_columns(site, table):
    path = config.RAW_DIR / site / f"{table}.xml"
    if not path.exists():
        pytest.skip(f"{path} not available (drive not mounted?)")
    for i, raw in enumerate(iter_rows(path)):
        convert_row(table, raw)  # strict: raises on a column missing from SCHEMAS
        if i >= 50_000:
            break
