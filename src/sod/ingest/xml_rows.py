"""Streaming reader for Stack Exchange dump XML (`<table><row .../>...</table>`).

Rows are yielded one at a time and freed immediately, so memory stays flat even
for the 185 GB PostHistory.xml. Missing attributes mean NULL (see the schema doc).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from datetime import datetime
from pathlib import Path
from typing import IO, Any, Literal

from lxml import etree

ColType = Literal["int", "datetime", "str", "bool"]

SCHEMAS: dict[str, dict[str, ColType]] = {
    "Posts": {
        "Id": "int",
        "PostTypeId": "int",
        "AcceptedAnswerId": "int",
        "ParentId": "int",
        "CreationDate": "datetime",
        "DeletionDate": "datetime",
        "Score": "int",
        "ViewCount": "int",
        "Body": "str",
        "OwnerUserId": "int",
        "OwnerDisplayName": "str",
        "LastEditorUserId": "int",
        "LastEditorDisplayName": "str",
        "LastEditDate": "datetime",
        "LastActivityDate": "datetime",
        "Title": "str",
        "Tags": "str",
        "AnswerCount": "int",
        "CommentCount": "int",
        "FavoriteCount": "int",
        "ClosedDate": "datetime",
        "CommunityOwnedDate": "datetime",
        "ContentLicense": "str",
    },
    "Users": {
        "Id": "int",
        "Reputation": "int",
        "CreationDate": "datetime",
        "DisplayName": "str",
        "LastAccessDate": "datetime",
        "WebsiteUrl": "str",
        "Location": "str",
        "AboutMe": "str",
        "Views": "int",
        "UpVotes": "int",
        "DownVotes": "int",
        "ProfileImageUrl": "str",
        "EmailHash": "str",
        "AccountId": "int",
    },
    "Votes": {
        "Id": "int",
        "PostId": "int",
        "VoteTypeId": "int",
        "UserId": "int",
        "CreationDate": "datetime",
        "BountyAmount": "int",
    },
    "Comments": {
        "Id": "int",
        "PostId": "int",
        "Score": "int",
        "Text": "str",
        "CreationDate": "datetime",
        "UserDisplayName": "str",
        "UserId": "int",
        "ContentLicense": "str",
    },
    "PostHistory": {
        "Id": "int",
        "PostHistoryTypeId": "int",
        "PostId": "int",
        "RevisionGUID": "str",
        "CreationDate": "datetime",
        "UserId": "int",
        "UserDisplayName": "str",
        "Comment": "str",
        "Text": "str",
        "ContentLicense": "str",
    },
    "PostLinks": {
        "Id": "int",
        "CreationDate": "datetime",
        "PostId": "int",
        "RelatedPostId": "int",
        "LinkTypeId": "int",
    },
    "Tags": {
        "Id": "int",
        "TagName": "str",
        "Count": "int",
        "ExcerptPostId": "int",
        "WikiPostId": "int",
        "IsModeratorOnly": "bool",
        "IsRequired": "bool",
    },
    "Badges": {
        "Id": "int",
        "UserId": "int",
        "Name": "str",
        "Date": "datetime",
        "Class": "int",
        "TagBased": "bool",
    },
}


class UnknownColumnError(ValueError):
    """A row has an attribute that is not in SCHEMAS (the dump format changed)."""


def iter_rows(
    source: str | Path | IO[bytes], columns: Iterable[str] | None = None
) -> Iterator[dict[str, str]]:
    """Yield each `<row>` as a dict of raw attribute strings, in file order.

    `source` is a path or a binary file object (e.g. one that counts bytes read).
    With `columns`, only those attributes are returned (absent ones are omitted).
    """
    wanted = tuple(columns) if columns is not None else None
    if isinstance(source, (str, Path)):
        source = str(source)
    context = etree.iterparse(source, events=("end",), tag="row", huge_tree=True)
    for _, el in context:
        attrib = el.attrib
        if wanted is None:
            yield dict(attrib)
        else:
            yield {c: attrib[c] for c in wanted if c in attrib}
        el.clear()
        parent = el.getparent()
        while el.getprevious() is not None:
            del parent[0]
    del context


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _parse_bool(value: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise ValueError(f"not a boolean: {value!r}")


_CONVERTERS = {"int": int, "datetime": parse_datetime, "str": str, "bool": _parse_bool}


def convert_row(table: str, raw: dict[str, str], strict: bool = True) -> dict[str, Any]:
    """Convert raw attribute strings to typed values; every schema column is present."""
    schema = SCHEMAS[table]
    if strict:
        unknown = raw.keys() - schema.keys()
        if unknown:
            raise UnknownColumnError(f"{table}: unknown column(s) {sorted(unknown)}")
    out: dict[str, Any] = {}
    for col, typ in schema.items():
        value = raw.get(col)
        out[col] = None if value is None else _CONVERTERS[typ](value)
    return out


_TAG_PIPE = re.compile(r"[^|]+")
_TAG_ANGLE = re.compile(r"<([^>]+)>")


def parse_tags(raw: str | None) -> list[str]:
    """Split a Tags value. Newer dumps use `|a|b|`; older ones use `<a><b>`."""
    if not raw:
        return []
    if raw.startswith("<"):
        return _TAG_ANGLE.findall(raw)
    return _TAG_PIPE.findall(raw)
