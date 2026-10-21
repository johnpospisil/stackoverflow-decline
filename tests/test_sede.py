import pytest

from sod.build.sede import db_to_site


@pytest.mark.parametrize(
    ("db", "site"),
    [
        ("StackOverflow", "stackoverflow.com"),
        ("StackExchange.Math", "math.stackexchange.com"),
        ("StackExchange.Ubuntu", "askubuntu.com"),
        ("StackExchange.Programmers", "softwareengineering.stackexchange.com"),
        ("StackOverflow.Br", "pt.stackoverflow.com"),
        ("SuperUser", "superuser.com"),
        ("StackExchange.Tex", None),  # not one of our sites
    ],
)
def test_db_to_site(db, site):
    assert db_to_site(db) == site
