# ruff: noqa: E501  (long column descriptions are data)
"""P32: the published dataset (weekly/monthly site and tag panels) for Hugging Face and Kaggle.

Builds <SOD_DATA_DIR>/release/stackoverflow-decline-panels-2026q3/ with Parquet + CSV panels,
the tag estimates, a column dictionary, SHA-256 checksums and the data card (README.md, with
Hugging Face YAML front matter). Nothing is uploaded: the user decides (see the data card's
checklist). Derived counts only: no post text, titles or user names or IDs.

Usage: python -m sod.release
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd

from sod import config

NAME = "stackoverflow-decline-panels-2026q3"
OUT = config.DATA_DIR / "release" / NAME
PANELS = ("site_week", "site_month", "tag_week", "tag_month")

# column -> (unit/type, meaning). Shared by all panels unless noted.
COLUMNS = {
    "period": ("date", "Start of the period: Monday of the week (UTC) or first day of the month"),
    "site": ("text", "Stack Exchange site, e.g. stackoverflow.com (site panels)"),
    "site_group": (
        "text",
        "treated (Stack Overflow), so_language, tech_exposed, donor (non-programming comparison sites) or context (Meta Stack Overflow) (site panels)",
    ),
    "tag": ("text", "Stack Overflow tag, as it was when the question was asked (tag panels)"),
    "tag_group": (
        "text",
        "top300 (largest tags of 2019-21) or new_post2021 (first used after 2021-09-30, >= 200 questions) (tag panels)",
    ),
    "tag_kind": (
        "text",
        "top300: hand-assigned family (language, framework, data_ml, ...); new_post2021: new / version / feature (tag panels)",
    ),
    "questions": (
        "count",
        "New questions created in the period (questions deleted before the dump are not included)",
    ),
    "active_askers": ("count", "Distinct users who asked at least one question in the period"),
    "answered_ever": ("count", "Questions with at least one answer by the dump date"),
    "eligible_24h": (
        "count",
        "Questions whose 24-hour window ends before the 2026-09-30 cut-off (denominator for answered_24h)",
    ),
    "answered_24h": ("count", "Questions answered within 24 hours (among eligible_24h)"),
    "eligible_7d": ("count", "Questions whose 7-day window ends before the cut-off"),
    "answered_7d": ("count", "Questions answered within 7 days (among eligible_7d)"),
    "eligible_30d": ("count", "Questions whose 30-day window ends before the cut-off"),
    "accepted_30d": (
        "count",
        "Questions with an answer accepted within 30 days (among eligible_30d)",
    ),
    "closed": ("count", "Questions ever closed (by the dump date)"),
    "closed_duplicate": ("count", "Questions closed as duplicates (by the dump date)"),
    "with_code": ("count", "Questions with at least one code block"),
    "median_hours_to_first_answer": (
        "hours",
        "Median hours to the first answer, among questions answered (by the dump date); recent periods are biased low",
    ),
    "answers": ("count", "New answers created in the period (site panels)"),
    "active_answerers": (
        "count",
        "Distinct users who posted at least one answer in the period (site panels)",
    ),
    "new_posters": (
        "count",
        "Users whose first question or answer on the site is in the period (site panels)",
    ),
    "questions_incl_deleted": (
        "count",
        "Questions including later-deleted ones, from the Stack Exchange Data Explorer (SEDE), 2019-01 onward; empty where not available (site_month only)",
    ),
    "partial_period": (
        "flag",
        "The period is not fully inside the dump (first partial week/month or after the cut-off)",
    ),
    "final_8_weeks": (
        "flag",
        "The period starts in the last 8 weeks before the cut-off: answers and closures may still be arriving",
    ),
}

TAG_EST_COLUMNS = {
    "tag": "Stack Overflow tag",
    "family": "Hand-assigned tag family",
    "size_2019_2021": "Questions in 2019-2021 (tags at time of asking)",
    "age_years_at_break": "Years from the tag's first question to 2022-11-30",
    "pct": "Average monthly gap vs the tag's own extended 2017-22 trend, Dec 2022 - Sep 2026, % (hierarchical negative binomial, posterior mean)",
    "pct_low": "95% credible interval, lower (%)",
    "pct_high": "95% credible interval, upper (%)",
    "questions_2021": "Questions in 2021",
    "questions_2025": "Questions in 2025",
    "plain_change_2021_2025_pct": "Plain change in questions, 2021 to 2025, % (no trend assumed)",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def panel(name: str) -> pd.DataFrame:
    d = pd.read_parquet(config.PANEL_DIR / f"{name}.parquet")
    if "site" in d.columns:
        d.insert(2, "site_group", d["site"].map(config.site_group))
    d["period"] = d["period"].dt.date
    return d


def tag_estimates() -> pd.DataFrame:
    t = pd.read_csv(config.REPORT_DIR / "tables" / "tag_effects.csv")
    m = pd.read_parquet(
        config.PANEL_DIR / "tag_month.parquet", columns=["period", "tag", "questions"]
    )
    y = m.assign(y=m["period"].dt.year).groupby(["tag", "y"])["questions"].sum().unstack()
    t["questions_2021"] = t["tag"].map(y[2021]).astype("Int64")
    t["questions_2025"] = t["tag"].map(y[2025]).astype("Int64")
    t["plain_change_2021_2025_pct"] = (
        (100 * (t["questions_2025"] / t["questions_2021"] - 1)).astype(float).round(1)
    )
    cols = list(TAG_EST_COLUMNS)
    return t[cols].round({"pct": 1, "pct_low": 1, "pct_high": 1, "age_years_at_break": 2})


def build() -> dict:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "data").mkdir(parents=True)
    files: dict[str, pd.DataFrame] = {n: panel(n) for n in PANELS}
    files["tag_estimates"] = tag_estimates()
    stats = {}
    for name, d in files.items():
        d.to_parquet(OUT / "data" / f"{name}.parquet", index=False, compression="zstd")
        d.to_csv(OUT / "data" / f"{name}.csv", index=False)
        stats[name] = {
            "rows": len(d),
            "columns": len(d.columns),
            "periods": [str(d["period"].min()), str(d["period"].max())] if "period" in d else None,
        }
    dictionary = [
        {"column": c, "type": t, "description": desc} for c, (t, desc) in COLUMNS.items()
    ] + [
        {"column": c, "type": "", "description": f"(tag_estimates) {d}"}
        for c, d in TAG_EST_COLUMNS.items()
    ]
    pd.DataFrame(dictionary).to_csv(OUT / "columns.csv", index=False)
    (OUT / "README.md").write_text(card(stats))
    sums = {
        str(p.relative_to(OUT)): sha256(p)
        for p in sorted(OUT.rglob("*"))
        if p.is_file() and p.name != "SHA256SUMS"
    }
    (OUT / "SHA256SUMS").write_text("".join(f"{h}  {p}\n" for p, h in sums.items()))
    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    out = {"dir": str(OUT), "files": stats, "total_mb": round(size / 1e6, 1)}
    (config.REPORT_DIR / "qa" / "release_summary.json").write_text(json.dumps(out, indent=2))
    return out


def _table(stats: dict) -> str:
    rows = [
        f"| `data/{n}.parquet` / `.csv` | {s['rows']:,} | {s['columns']} | "
        + (f"{s['periods'][0]} to {s['periods'][1]}" if s["periods"] else "–")
        + " |"
        for n, s in stats.items()
    ]
    return "| File | Rows | Columns | Periods |\n|---|---|---|---|\n" + "\n".join(rows)


def _dictionary() -> str:
    rows = [f"| `{c}` | {t} | {d} |" for c, (t, d) in COLUMNS.items()]
    rows += [f"| `{c}` | | {d} |" for c, d in TAG_EST_COLUMNS.items()]
    return "| Column | Type | Meaning |\n|---|---|---|\n" + "\n".join(rows)


def card(stats: dict) -> str:
    configs = "\n".join(f"  - config_name: {n}\n    data_files: data/{n}.parquet" for n in stats)
    return f"""---
license: cc-by-sa-4.0
pretty_name: Stack Overflow and Stack Exchange activity panels, 2008-2026 (2026-Q3 dump)
language:
  - en
tags:
  - stack-overflow
  - stack-exchange
  - time-series
  - generative-ai
  - chatgpt
size_categories:
  - 100K<n<1M
configs:
{configs}
---

# Stack Overflow and Stack Exchange activity panels, 2008–2026

Weekly and monthly counts of questions, answers, users and response times for **27 Stack
Exchange sites** and the **363 Stack Overflow tags** analysed in *What happened to Stack
Overflow?* (John Pospisil, 2026). Built from the official Stack Exchange data dump, 2026-Q3
release (cut-off 2026-09-30). **Derived counts only**: no post text, titles, user names or user
IDs.

- Code, method and article: https://github.com/johnpospisil/stackoverflow-decline
- Not affiliated with or endorsed by Stack Overflow or Stack Exchange.

## Files

{_table(stats)}

`columns.csv` has the column dictionary below; `SHA256SUMS` has a checksum for every file.

- **Sites (27):** stackoverflow.com; Stack Overflow in Russian, Spanish, Portuguese and
  Japanese; six other tech sites (Super User, Server Fault, Ask Ubuntu, Unix & Linux, Software
  Engineering, Database Administrators); fifteen non-programming sites (Mathematics, Physics,
  Chemistry, Biology, English, Philosophy, History, Cooking, DIY, Travel, Bicycles, Gaming,
  Science Fiction, Movies, Role-playing Games); Meta Stack Overflow. `site_group` says which.
- **Tags:** the 300 largest Stack Overflow tags of 2019–21, and 69 tags first used after
  2021-09-30 with at least 200 questions. Tags are as they were **when each question was
  asked** (the first tag event in the post history), not today's tags.
- **tag_estimates:** each top tag's post-ChatGPT gap against its own trend from the
  project's hierarchical model (297 tags; three retired tags excluded), plus the plain
  2021→2025 change.

## Column dictionary

{_dictionary()}

## How it was made

The XML dump was streamed into Parquet, one row per post, and aggregated with DuckDB. Weeks
run Monday to Sunday, UTC. A question counts in the period it was created. Fixed-window
measures (answered within 24 hours, 7 days; accepted within 30 days) count only questions
whose whole window ends before the cut-off, so they are comparable over time. The full
pipeline (`make all`) rebuilds these files from the raw dump.

## Known limitations

- **Deleted posts are missing.** The dump omits posts deleted before the dump date. On Stack
  Overflow the deleted share of questions rose from about 34% (2017) to 53% (2026), so recent
  counts understate how many questions were asked. `questions_incl_deleted` (site_month,
  from SEDE, 2019 onward) gives the totals including deleted posts.
- **Counts as of the dump date.** Answers, closures and acceptances keep arriving after a
  question is asked; recent periods are incomplete (`final_8_weeks`), and
  `median_hours_to_first_answer` is biased low for recent periods. Prefer the fixed-window
  columns.
- **Closed questions are under-represented**, because closed questions are deleted more often.
- **Tag changes:** Stack Overflow retires, merges and renames tags (e.g. `excel-vba` 2020-08,
  `flutter-layout` 2022-12, `dockerfile` 2025-06); counts can drop to zero for that reason.
- **Platform changes affect series:** e.g. the 2023 moderator strike, Staging Ground for new
  askers (2024-06), opinion-based questions (2025-10), a read-only period (2026-08). See
  `data/reference/events.csv` in the repository.
- **The tag estimates depend on a trend assumption:** each tag's own 2017–22 trend is extended
  four years, which enlarges the gap for tags that were growing fast. Compare with
  `plain_change_2021_2025_pct`.
- **Dump integrity:** file hashes match the community-maintained checksum list; no watermark
  rows were found.

## Licence and attribution

Stack Exchange content is licensed **CC BY-SA 4.0** by its contributors (older posts CC BY-SA
2.5 or 3.0). This derived dataset is released under **CC BY-SA 4.0**. Please attribute:

> Derived from the Stack Exchange data dump (2026-Q3), contributed by Stack Exchange users and
> licensed CC BY-SA 4.0. Panels by John Pospisil, https://github.com/johnpospisil/stackoverflow-decline

The data dump is provided under Stack Exchange's access terms, which exclude training large
language models. This dataset contains aggregate counts only, but please don't use it to train
LLMs either.

## Citation

```bibtex
@misc{{pospisil2026stackoverflow,
  author = {{Pospisil, John}},
  title  = {{Stack Overflow and Stack Exchange activity panels, 2008--2026}},
  year   = {{2026}},
  note   = {{Derived from the Stack Exchange data dump, 2026-Q3. CC BY-SA 4.0}},
  url    = {{https://github.com/johnpospisil/stackoverflow-decline}}
}}
```
"""


def main() -> None:
    print(json.dumps(build(), indent=2))


if __name__ == "__main__":
    main()
