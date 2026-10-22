"""P31: precomputed data for the tag lookup app (app/data/tags.json).

For each of the 297 modelled top tags: weekly questions (from the tag's first week to the last
full week, 2026-09-21), the tag model's expected questions without ChatGPT (its own extended
pre-2022 trend, monthly posterior median and 95% band, shown as a weekly rate), the model's
average gap with its interval, and its rank (1 = fell most). For the post-2021 tags: weekly
questions and the gap against the lifecycle benchmark (they have no pre-period, so no line).

Derived counts only (CC BY-SA 4.0 attribution in the app). Usage: python -m sod.app_data
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from sod import config
from sod.models import tags as T

# The sample pipeline (SAMPLE=1) writes next to its own report, never over the real app data.
APP_DIR = config.REPORT_DIR.parent / "app" if config.SAMPLE else config.REPO_ROOT / "app"
OUT = APP_DIR / "data" / "tags.json"
LAST_WEEK = pd.Timestamp("2026-09-21")  # last full week before the cut-off


def weekly(groups: tuple[str, ...]) -> dict[str, dict]:
    w = pd.read_parquet(
        config.PANEL_DIR / "tag_week.parquet", columns=["period", "tag", "tag_group", "questions"]
    )
    w = w[w["tag_group"].isin(groups) & (w["period"] <= LAST_WEEK)]
    out = {}
    for tag, g in w.groupby("tag"):
        g = g.set_index("period")["questions"].sort_index()
        nz = g[g > 0]
        if nz.empty:
            continue
        g = g.loc[nz.index[0] :]
        out[tag] = {"w0": str(g.index[0].date()), "w": g.astype(int).tolist()}
    return out


def yearly_change() -> dict[str, dict]:
    """Questions in 2025 vs 2021 (whole years, no trend assumed): a check on the model's
    number, which extends each tag's own pre-2022 trend and so depends on that trend."""
    m = pd.read_parquet(
        config.PANEL_DIR / "tag_month.parquet", columns=["period", "tag", "questions"]
    )
    y = m.assign(y=m["period"].dt.year).groupby(["tag", "y"])["questions"].sum().unstack()
    out = {}
    for tag, r in y.iterrows():
        a, b = r.get(2021, 0), r.get(2025, 0)
        if a > 0:
            out[tag] = {"q21": int(a), "q25": int(b), "raw": round(100 * (b / a - 1), 1)}
    return out


def counterfactual() -> dict[str, dict]:
    cf = pd.read_parquet(config.MODEL_DIR / "tags_negbin_counterfactual.parquet")
    per_week = 7 / cf["period"].dt.days_in_month
    out = {}
    for tag, g in cf.assign(
        m=cf["cf_median"] * per_week, lo=cf["cf_low"] * per_week, hi=cf["cf_high"] * per_week
    ).groupby("tag"):
        g = g.sort_values("period")
        out[tag] = {
            "m0": str(g["period"].iloc[0].date()),
            "cf": np.round(g["m"], 1).tolist(),
            "cl": np.round(g["lo"], 1).tolist(),  # band low / high
            "ch": np.round(g["hi"], 1).tolist(),
        }
    return out


def build() -> dict:
    eff = pd.read_csv(config.REPORT_DIR / "tables" / "tag_effects.csv")
    eff = eff.sort_values("pct").reset_index(drop=True)
    eff["rank"] = np.arange(1, len(eff) + 1)
    new = pd.read_csv(config.REPORT_DIR / "tables" / "new_tags_lifecycle.csv")
    retired = T.retired_tags()
    W = weekly(("top300", "new_post2021"))
    CF = counterfactual()
    RAW = yearly_change()
    tags = []
    for r in eff.itertuples():
        tags.append(
            {
                "tag": r.tag,
                "kind": "top",
                "family": r.family,
                "pct": round(r.pct, 1),
                "lo": round(r.pct_low, 1),
                "hi": round(r.pct_high, 1),
                "rank": int(r.rank),
                "size": int(r.size_2019_2021),
                **RAW.get(r.tag, {}),
                **W.get(r.tag, {}),
                **CF.get(r.tag, {}),
            }
        )
    for r in new.dropna(subset=["gap_pct"]).itertuples():
        if r.tag in retired:
            continue
        tags.append(
            {
                "tag": r.tag,
                "kind": "new",
                "family": r.kind,  # new technology / version / feature
                "pct": round(r.gap_pct, 1),
                "n_questions": int(r.n_questions),
                **W.get(r.tag, {}),
            }
        )
    return {
        "n_ranked": int(len(eff)),
        "median_pct": round(float(eff["pct"].median()), 1),
        "last_week": str(LAST_WEEK.date()),
        "break": str(config.BREAK_WEEK),
        "tags": tags,
    }


def main() -> None:
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":")))
    print(f"{len(data['tags'])} tags -> {OUT} ({OUT.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
