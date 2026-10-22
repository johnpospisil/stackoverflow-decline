"""P21: question mix, 2021 vs 2025 (H3; PREREGISTRATION.md section 6 and deviation 2026-10-21).

Measures (H3): median body length, share with code blocks, share first closed as duplicate
within 30 days, share from first-time askers. Descriptive extras: text length, title length,
share closed within 30 days, share answered within 7 days, median score, median asker
account age.

Tag-mix reweighting: each question spreads weight 1/n_tags over its tags (top-300 tags plus an
"other" bucket); 2025 questions are reweighted to 2021 tag shares. Within-tag change =
reweighted 2025 - 2021; composition = actual 2025 - reweighted 2025. 95% intervals: Poisson
bootstrap (200 replicates, tag shares recomputed in each). Deleted questions: Lee bounds that
trim 2021 by the survival difference (15.5%).

Usage: python -m sod.models.question_mix
"""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from sod import config, progress  # noqa: E402
from sod.db import connect  # noqa: E402

JOB = "question_mix"
YEARS = (2021, 2025)
DUPLICATE_REASON = 101
REPS = 20 if config.SAMPLE else 200
SEED = 21
SURVIVAL = {2021: 1 - 0.418, 2025: 1 - 0.508}  # from SEDE (P09 / site_month panel)
QA = config.REPORT_DIR / "qa"
TABLES = config.REPORT_DIR / "tables"

# name: (column, statistic, predicted direction for H3 or None, label)
MEASURES = {
    "body_length": ("body_chars", "median", +1, "Median body length (characters)"),
    "code_share": ("code", "mean", +1, "Share with a code block"),
    "dup_share": ("dup30", "mean", -1, "Share closed as duplicate within 30 days"),
    "first_time_share": ("first_time", "mean", -1, "Share from first-time askers"),
    "text_length": ("text_chars", "median", None, "Median text length (excl. code)"),
    "title_length": ("title_chars", "median", None, "Median title length"),
    "closed_share": ("closed30", "mean", None, "Share closed within 30 days"),
    "answered_7d": ("answered7d", "mean", None, "Share answered within 7 days"),
    "positive_score": ("pos_score", "mean", None, "Share with score > 0 (as of 2026-09)"),
    "account_age": ("asker_account_age_days", "median", None, "Median asker account age (days)"),
}
H3 = [k for k, v in MEASURES.items() if v[2] is not None]


# --- data ------------------------------------------------------------------------------


def load() -> pd.DataFrame:
    con = connect()
    df = con.execute(
        f"""
        SELECT year(CreationDate) AS year, tags, n_tags, body_chars, text_chars, title_chars,
               n_code_blocks >= 1 AS code,
               coalesce(first_close_reason = {DUPLICATE_REASON}
                        AND first_close_at <= CreationDate + INTERVAL 30 DAY, false) AS dup30,
               coalesce(first_close_at <= CreationDate + INTERVAL 30 DAY, false) AS closed30,
               CASE WHEN owner_deleted THEN NULL ELSE asker_first_post END AS first_time,
               coalesce(hours_to_first_answer <= 168, false) AS answered7d,
               (Score > 0)::DOUBLE AS pos_score, asker_account_age_days
        FROM read_parquet('{config.PARQUET_DIR}/questions/*/*.parquet')
        WHERE site = '{config.TREATED}' AND year(CreationDate) IN {YEARS}
        ORDER BY Id  -- fixed row order, so the bootstrap draws are reproducible
        """
    ).df()
    for c in ("code", "dup30", "closed30", "answered7d"):
        df[c] = df[c].astype(float)
    df["first_time"] = df["first_time"].astype(float)
    return df.reset_index(drop=True)


def explode_tags(
    df: pd.DataFrame, top: set[str]
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """Rows: (question index, bucket index, fractional weight)."""
    e = df[["tags", "n_tags"]].explode("tags")
    bucket = e["tags"].where(e["tags"].isin(top), "__other").fillna("__other")
    names = sorted(bucket.unique())
    code = bucket.map({n: i for i, n in enumerate(names)}).to_numpy()
    frac = 1.0 / e["n_tags"].clip(lower=1).to_numpy()
    return e.index.to_numpy(), code, frac, names


# --- weighted statistics ---------------------------------------------------------------


def wstat(x: np.ndarray, w: np.ndarray, stat: str, order: np.ndarray | None = None) -> float:
    """Weighted mean or median, NaNs ignored. `order` (argsort of x, NaNs last) can be passed
    to avoid re-sorting in bootstrap loops."""
    if stat == "mean":
        ok = ~np.isnan(x)
        return float(np.sum(x[ok] * w[ok]) / np.sum(w[ok]))
    if order is None:
        order = np.argsort(x, kind="stable")
    order = order[~np.isnan(x[order])]
    cw = np.cumsum(w[order])
    return float(x[order][np.searchsorted(cw, 0.5 * cw[-1])])


_ORDERS: dict = {}


def _order(x: np.ndarray, key) -> np.ndarray:
    if key not in _ORDERS:
        _ORDERS[key] = np.argsort(x, kind="stable")
    return _ORDERS[key]


def reweight(year: np.ndarray, qidx, code, frac, base_w: np.ndarray) -> np.ndarray:
    """Weights making 2025 tag shares equal 2021's (2021 rows keep their base weight)."""
    n_b = code.max() + 1
    out = base_w.copy()
    shares = {}
    for y in YEARS:
        rows = year[qidx] == y
        s = np.bincount(code[rows], weights=frac[rows] * base_w[qidx[rows]], minlength=n_b)
        shares[y] = s / s.sum()
    ratio = np.divide(shares[2021], shares[2025], out=np.zeros(n_b), where=shares[2025] > 0)
    rows = year[qidx] == 2025
    w25 = np.bincount(qidx[rows], weights=frac[rows] * ratio[code[rows]], minlength=len(base_w))
    m25 = year == 2025
    out[m25] = base_w[m25] * w25[m25]
    return out


def compute(df, qidx, code, frac, base_w) -> dict:
    year = df["year"].to_numpy()
    rw = reweight(year, qidx, code, frac, base_w)
    out = {}
    for name, (col, stat, _, _) in MEASURES.items():
        x = df[col].to_numpy(dtype=float)
        x21, x25 = x[year == 2021], x[year == 2025]
        o21, o25 = _order(x21, (id(df), col, 2021)), _order(x25, (id(df), col, 2025))
        m21 = wstat(x21, base_w[year == 2021], stat, o21)
        m25 = wstat(x25, base_w[year == 2025], stat, o25)
        m25r = wstat(x25, rw[year == 2025], stat, o25)
        out[name] = {
            "y2021": m21,
            "y2025": m25,
            "y2025_tagmix2021": m25r,
            "total": m25 - m21,
            "within": m25r - m21,
            "composition": m25 - m25r,
        }
    return out


def lee_bounds_2021(x: np.ndarray, stat: str, trim: float) -> tuple[float, float]:
    """2021 statistic after dropping `trim` of the sample from the bottom / top of x."""
    x = np.sort(x[~np.isnan(x)])
    k = int(round(trim * len(x)))
    lo_sample, hi_sample = x[: len(x) - k], x[k:]
    f = np.median if stat == "median" else np.mean
    return float(f(lo_sample)), float(f(hi_sample))


# --- figure ----------------------------------------------------------------------------


def fig_slopes(res: dict, path) -> None:
    names = list(MEASURES)
    fig, axes = plt.subplots(2, 5, figsize=(15, 6))
    for ax, name in zip(axes.flat, names, strict=True):
        r = res[name]
        _, stat, pred, label = MEASURES[name]
        ax.plot(
            [0, 1], [r["y2021"], r["y2025"]], "o-", color="#999999", lw=1.5, label="actual 2025"
        )
        ax.plot(
            [0, 1],
            [r["y2021"], r["y2025_tagmix2021"]],
            "o-",
            color="#D55E00",
            lw=2,
            label="2025 at 2021 tag mix",
        )
        fmt = (lambda v: f"{100 * v:.1f}%") if stat == "mean" else (lambda v: f"{v:,.0f}")
        for xpos, v, c in (
            (0, r["y2021"], "#333333"),
            (1, r["y2025"], "#999999"),
            (1, r["y2025_tagmix2021"], "#D55E00"),
        ):
            ax.annotate(
                fmt(v),
                (xpos, v),
                fontsize=7,
                color=c,
                xytext=(6 if xpos else -6, 0),
                textcoords="offset points",
                ha="left" if xpos else "right",
                va="center",
            )
        ax.set_xticks([0, 1], ["2021", "2025"])
        ax.set_xlim(-0.6, 1.6)
        title = label + ("" if pred is None else f"\nH3 predicts {'up' if pred > 0 else 'down'}")
        ax.set_title(title, fontsize=8, loc="left")
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=7)
    axes.flat[0].legend(fontsize=7, frameon=False)
    fig.suptitle(
        "Stack Overflow questions, 2021 vs 2025 (orange: tag mix held at 2021)",
        x=0.01,
        ha="left",
        fontsize=11,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# --- run -------------------------------------------------------------------------------


def run() -> dict:
    progress.write_manifest(JOB, {"load": 2, "point": 1, "bootstrap": REPS, "write": 1})
    rep = progress.Reporter(JOB, "load", 1)
    df = load()
    top = set(pd.read_csv(config.REFERENCE_DIR / "tag_families.csv")["tag"])
    qidx, code, frac, names = explode_tags(df, top)
    rep.finish(len(df))

    rep = progress.Reporter(JOB, "point", 1)
    base = np.ones(len(df))
    point = compute(df, qidx, code, frac, base)
    rep.finish(1)

    rep = progress.Reporter(JOB, "bootstrap", REPS)
    rng = np.random.default_rng(SEED)
    boots = []
    for i in range(REPS):
        boots.append(compute(df, qidx, code, frac, rng.poisson(1.0, len(df)).astype(float)))
        rep.update(i + 1, i + 1)
    rep.finish(REPS)

    rep = progress.Reporter(JOB, "write", 1)
    year = df["year"].to_numpy()
    trim = 1 - SURVIVAL[2025] / SURVIVAL[2021]
    rows, h3 = [], {}
    for name, (col, stat, pred, label) in MEASURES.items():
        r = point[name]
        ci = {
            k: [float(np.percentile([b[name][k] for b in boots], q)) for q in (2.5, 97.5)]
            for k in ("total", "within", "composition")
        }
        lo21, hi21 = lee_bounds_2021(df.loc[year == 2021, col].to_numpy(dtype=float), stat, trim)
        lee = sorted([r["y2025_tagmix2021"] - hi21, r["y2025_tagmix2021"] - lo21])
        row = {
            "measure": name,
            "label": label,
            "predicted": pred,
            **r,
            "within_ci": ci["within"],
            "total_ci": ci["total"],
            "composition_ci": ci["composition"],
            "within_lee_bounds": lee,
        }
        if pred is not None:
            in_dir = (pred > 0 and ci["within"][0] > 0) or (pred < 0 and ci["within"][1] < 0)
            row["moves_as_predicted"] = bool(in_dir)
            row["lee_bounds_same_sign"] = bool(
                (pred > 0 and lee[0] > 0) or (pred < 0 and lee[1] < 0)
            )
            h3[name] = bool(in_dir)
        rows.append(row)
    n_ok = sum(h3.values())
    summary = {
        "n_questions": {str(y): int((year == y).sum()) for y in YEARS},
        "tag_buckets": len(names),
        "lee_trim_share_2021": trim,
        "measures": rows,
        "h3_measures_as_predicted": h3,
        "h3_n_as_predicted": n_ok,
        "h3_supported": n_ok >= 3,
    }
    TABLES.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(TABLES / "question_mix.csv", index=False)
    (QA / "question_mix_summary.json").write_text(json.dumps(summary, indent=2, default=float))
    fig_slopes(point, config.FIGURE_DIR / "question_mix_slopes.png")
    rep.finish(1)
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=float))
