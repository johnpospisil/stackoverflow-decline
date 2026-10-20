from pathlib import Path

import pytest

from sod.ingest.body_features import body_features, title_features
from sod.ingest.xml_rows import convert_row, iter_rows

FIXTURES = Path(__file__).parent / "fixtures" / "sample.stackexchange.com"


@pytest.fixture(scope="module")
def posts() -> dict[int, dict]:
    return {
        r["Id"]: r for r in (convert_row("Posts", raw) for raw in iter_rows(FIXTURES / "Posts.xml"))
    }


def test_question_with_one_block_and_inline_code(posts):
    f = body_features(posts[5]["Body"])
    assert f["n_code_blocks"] == 1
    assert f["n_inline_code"] == 2
    assert f["code_chars"] == len("x = [1, 2, 3]\n")
    # visible prose outside <pre> blocks, whitespace collapsed
    assert f["text_chars"] == len(
        "How do I reverse a list in Python? I tried x.reverse() but it returns None."
    )
    assert f["n_links"] == 0
    assert f["n_images"] == 0
    assert f["body_chars"] == len(posts[5]["Body"])


def test_answer_with_link_and_crlf(posts):
    f = body_features(posts[9]["Body"])
    assert f["n_code_blocks"] == 1
    assert f["code_chars"] == len("x[::-1]\n")
    assert f["n_links"] == 1
    assert f["text_chars"] == len("Use slicing: See the docs.")


def test_two_blocks_and_image(posts):
    f = body_features(posts[13]["Body"])
    assert f["n_code_blocks"] == 2
    assert f["code_chars"] == len("a") + len("b\nc")
    assert f["n_images"] == 1
    assert f["n_inline_code"] == 0
    assert f["text_chars"] == len("Two blocks:")


def test_unicode_counts_code_points(posts):
    f = body_features(posts[7]["Body"])
    assert f["text_chars"] == len("Why is my code slow? \U0001f600 日本語 العربية")
    assert f["n_code_blocks"] == 0


def test_html_entities_inside_body_are_decoded():
    f = body_features("<p>a &lt; b &amp;&amp; c</p><pre><code>x &gt; 1</code></pre>")
    assert f["text_chars"] == len("a < b && c")
    assert f["code_chars"] == len("x > 1")


@pytest.mark.parametrize("body", ["", None])
def test_empty_body(body):
    f = body_features(body)
    assert f == {
        "body_chars": 0,
        "text_chars": 0,
        "code_chars": 0,
        "n_code_blocks": 0,
        "n_inline_code": 0,
        "n_links": 0,
        "n_images": 0,
    }


def test_title_features(posts):
    assert title_features(posts[7]["Title"]) == {"title_chars": 33, "title_words": 7}
    assert title_features(posts[20]["Title"]) == {"title_chars": 27, "title_words": 4}
    assert title_features(None) == {"title_chars": 0, "title_words": 0}
