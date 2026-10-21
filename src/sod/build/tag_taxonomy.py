"""P11: features for the top 300 Stack Overflow tags, using pre-ChatGPT data only.

Inputs: data/reference/tag_families.csv (hand-classified), questions Parquet.
Outputs:
  data/reference/tag_features.csv       top 300 tags (family, age, size, maturity, stock)
  data/reference/tags_new_post2021.csv  tags first used after 2021-09-30 with >= 200 questions
                                        (the H2 "thin training data" group)

All features come from questions created before the break, except `first_seen`
(earliest question ever) and the >= 200 total-question threshold for new tags,
which the pre-registration defines over the whole period.

Usage: python -m sod.build.tag_taxonomy
"""

from __future__ import annotations

import pandas as pd

from sod import config
from sod.db import connect

FAMILIES = config.REFERENCE_DIR / "tag_families.csv"
FEATURES = config.REFERENCE_DIR / "tag_features.csv"
NEW_TAGS = config.REFERENCE_DIR / "tags_new_post2021.csv"
TRAINING_CUTOFF = "2021-10-01"  # first ChatGPT models' training data ends 2021-09
NEW_TAG_MIN_QUESTIONS = 200


def _questions_view(con) -> None:
    con.execute(
        "CREATE OR REPLACE VIEW soq AS SELECT * FROM read_parquet("
        f"'{config.PARQUET_DIR}/questions/site={config.TREATED}/*.parquet')"
    )


def tag_features(con) -> pd.DataFrame:
    fam = pd.read_csv(FAMILIES)
    con.register("fam", fam)
    df = con.execute(
        f"""
        WITH t AS (
            SELECT unnest(tags) AS tag, CreationDate, closed_as_duplicate FROM soq
        ),
        first_any AS (  -- earliest question carrying the tag, initial or current tags
            SELECT tag, min(CreationDate) AS first_seen FROM (
                SELECT unnest(tags) AS tag, CreationDate FROM soq
                UNION ALL SELECT unnest(tags_current) AS tag, CreationDate FROM soq
            ) GROUP BY 1
        )
        SELECT fam.rank_2019_2021, fam.tag, fam.family,
               f.first_seen,
               date_diff('day', f.first_seen, DATE '{config.BREAK_DATE}') / 365.25
                   AS age_years_at_break,
               count(*) FILTER (WHERE t.CreationDate >= '2019-01-01'
                                  AND t.CreationDate < '2022-01-01') AS size_2019_2021,
               count(*) FILTER (WHERE t.CreationDate < '{TRAINING_CUTOFF}') AS stock_to_2021_09,
               avg(t.closed_as_duplicate::INT) FILTER (
                   WHERE t.CreationDate >= '2019-01-01' AND t.CreationDate < '2022-01-01'
               ) AS dup_share_2019_2021
        FROM fam
        JOIN t ON t.tag = fam.tag
        JOIN first_any f ON f.tag = fam.tag
        GROUP BY ALL
        ORDER BY fam.rank_2019_2021
        """
    ).df()
    return df


def new_tags(con) -> pd.DataFrame:
    return con.execute(
        f"""
        WITH first_any AS (
            SELECT tag, min(CreationDate) AS first_seen FROM (
                SELECT unnest(tags) AS tag, CreationDate FROM soq
                UNION ALL SELECT unnest(tags_current) AS tag, CreationDate FROM soq
            ) GROUP BY 1
        ),
        n AS (SELECT tag, count(*) AS n_questions FROM (SELECT unnest(tags) AS tag FROM soq) GROUP BY 1)
        SELECT f.tag, f.first_seen, n.n_questions
        FROM first_any f JOIN n USING (tag)
        WHERE f.first_seen >= '{TRAINING_CUTOFF}' AND n.n_questions >= {NEW_TAG_MIN_QUESTIONS}
        ORDER BY n.n_questions DESC
        """
    ).df()


def main() -> None:
    con = connect()
    _questions_view(con)
    feats = tag_features(con)
    feats.to_csv(FEATURES, index=False, float_format="%.6g")
    new = new_tags(con)
    new.to_csv(NEW_TAGS, index=False)
    print(f"{len(feats)} tag features -> {FEATURES.name}; {len(new)} new tags -> {NEW_TAGS.name}")


if __name__ == "__main__":
    main()
