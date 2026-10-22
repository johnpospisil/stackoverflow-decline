"""P20: the "thin training data" test (H2; PREREGISTRATION.md section 6 and deviations).

(a) Age: the H2 model's tag-age coefficient (P19 refit without retired tags). H2(a) is
    supported if its 95% interval is below 0 (older tags decline more). Also shown with a
    control for each tag's pre-2022 trend (per-draw regression of the tag effects).
(b) New tags: tags first used after 2021-09-30 (>= 200 questions), measured with a lifecycle
    benchmark (deviation 2026-10-21): each new tag vs pre-ChatGPT tags of similar early size
    at the same age. H2(b) is supported if the new tags' median gap is smaller in magnitude
    than the median top-300 tag's and the 95% interval for the difference excludes 0.
    Secondary: kind = new vs version/feature. Calibration: the same method before ChatGPT.

Usage: python -m sod.models.thin_data
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
from sod.models import tags as T  # noqa: E402

JOB = "thin_data"
CUTOFF_MONTH = pd.Timestamp("2026-09-01")
MIN_QUESTIONS = 200
ANCHOR_MONTHS = (1, 2, 3)
FIRST_GAP_MONTH = 4
B = 4000
SEED = 7
QA = config.REPORT_DIR / "qa"
TABLES = config.REPORT_DIR / "tables"


# --- data ------------------------------------------------------------------------------


def tag_life_counts(min_first="2014-01-01", min_total=50) -> pd.DataFrame:
    """Monthly question counts for Stack Overflow tags first used on or after `min_first`
    (tags at the time of asking), zero-filled from the first month to the cut-off."""
    con = connect()
    df = con.execute(
        f"""
        WITH t AS (
            SELECT unnest(tags) AS tag, date_trunc('month', CreationDate)::DATE AS m
            FROM read_parquet('{config.PARQUET_DIR}/questions/*/*.parquet')
            WHERE site = '{config.TREATED}'
        ),
        f AS (
            SELECT tag, min(m) AS first_m FROM t GROUP BY tag
            HAVING min(m) >= DATE '{min_first}' AND count(*) >= {min_total}
        )
        SELECT tag, first_m, m, count(*) AS q FROM t JOIN f USING (tag) GROUP BY ALL
        """
    ).df()
    df["first_m"] = pd.to_datetime(df["first_m"])
    df["m"] = pd.to_datetime(df["m"])
    out = []
    for (tag, first), g in df.groupby(["tag", "first_m"]):
        idx = pd.date_range(first, CUTOFF_MONTH, freq="MS")
        s = g.set_index("m")["q"].reindex(idx, fill_value=0)
        out.append(
            pd.DataFrame(
                {"tag": tag, "first_m": first, "k": np.arange(len(idx)), "q": s.to_numpy()}
            )
        )
    return pd.concat(out, ignore_index=True)


def wide(life: pd.DataFrame, tags, max_k: int, end: pd.Timestamp) -> pd.DataFrame:
    """tags x k matrix, NaN beyond each tag's observable follow-up (before `end`)."""
    sub = life[life["tag"].isin(tags)]
    first = sub["first_m"]
    obs = sub["k"] < ((end.year - first.dt.year) * 12 + end.month - first.dt.month + 1)
    w = sub[obs & (sub["k"] < max_k)].pivot(index="tag", columns="k", values="q")
    return w.reindex(columns=range(max_k))


# --- lifecycle benchmark -----------------------------------------------------------------


def anchor(row: np.ndarray) -> float:
    return float(np.nanmean(row[list(ANCHOR_MONTHS)]))


def lifecycle_gap(y: np.ndarray, refs: pd.DataFrame) -> dict:
    """y: the tag's counts by month of life (k = 0..F-1). refs: reference tags x k."""
    F = len(y)
    a = anchor(y)
    R = refs.to_numpy(dtype=float)
    ra = np.nanmean(R[:, list(ANCHOR_MONTHS)], axis=1)
    cum = np.nancumsum(R, axis=1)[:, F - 1] if R.shape[1] >= F else np.full(len(R), np.nan)
    ok_base = (ra > 0) & (cum >= MIN_QUESTIONS) & ~np.isnan(R[:, F - 1])
    for factor in (2, 3):
        ok = ok_base & (ra >= a / factor) & (ra <= a * factor)
        if ok.sum() >= 10:
            break
    if ok.sum() < 3 or a <= 0:
        return {"gap_log": np.nan, "n_refs": int(ok.sum()), "match_factor": factor}
    ratio = np.exp(np.nanmean(np.log((R[ok, :F] + 0.5) / ra[ok, None]), axis=0))
    cf = a * ratio
    ks = slice(FIRST_GAP_MONTH, F)
    gap = np.log(y[ks].sum() / cf[ks].sum())
    return {
        "gap_log": float(gap),
        "gap_pct": float(T.pct(gap)),
        "n_refs": int(ok.sum()),
        "match_factor": factor,
        "anchor": a,
        "months": int(F - FIRST_GAP_MONTH),
        "actual": float(y[ks].sum()),
        "counterfactual": float(cf[ks].sum()),
    }


def run_lifecycle(
    life, targets: pd.DataFrame, ref_first: tuple[str, str], end: pd.Timestamp, max_k: int
) -> pd.DataFrame:
    """targets: tag, first_m. Returns one row per target tag."""
    lo, hi = (pd.Timestamp(x) for x in ref_first)
    firsts = life.drop_duplicates("tag").set_index("tag")["first_m"]
    ref_tags = firsts[(firsts >= lo) & (firsts <= hi)].index
    refs = wide(life, ref_tags, max_k, end)
    rows = []
    for r in targets.itertuples():
        s = life[life["tag"] == r.tag].sort_values("k")
        F = (end.year - r.first_m.year) * 12 + end.month - r.first_m.month + 1
        y = s["q"].to_numpy(dtype=float)[: min(F, max_k)]
        if len(y) <= FIRST_GAP_MONTH:
            continue
        rows.append({"tag": r.tag, "first_m": r.first_m, **lifecycle_gap(y, refs)})
    return pd.DataFrame(rows)


# --- (a) age test --------------------------------------------------------------------------


def pre_slopes() -> pd.Series:
    t = pd.read_parquet(config.PANEL_DIR / "tag_month.parquet")
    t = t[(t["tag_group"] == "top300") & (t["period"] >= T.START) & (t["period"] <= T.PRE_END)]
    t = t[~t["period"].between(*T.COVID)]

    def slope(g):
        g = g[g["questions"] > 0]
        x = (g["period"] - g["period"].min()).dt.days / 365.25
        return np.polyfit(x, np.log(g["questions"]), 1)[0]

    return t.groupby("tag").apply(slope, include_groups=False).rename("pre_slope")


def age_with_pretrend(draws: pd.DataFrame, features: pd.DataFrame, n_draws=1000) -> dict:
    tags = features["tag"].tolist()
    f = features.set_index("tag").join(pre_slopes())
    f["z_pre_slope"] = (f["pre_slope"] - f["pre_slope"].mean()) / f["pre_slope"].std()
    fam = pd.get_dummies(f["family"], drop_first=True, dtype=float)
    X = np.column_stack(
        [np.ones(len(f)), f[T.PREDICTORS + ["z_pre_slope"]].to_numpy(), fam.to_numpy()]
    )
    D = draws[tags].to_numpy()
    rng = np.random.default_rng(SEED)
    pick = rng.choice(len(D), size=min(n_draws, len(D)), replace=False)
    coefs = np.array([np.linalg.lstsq(X, D[i], rcond=None)[0][1:5] for i in pick])
    names = T.PREDICTORS + ["z_pre_slope"]
    return {
        n: {
            "median": float(np.median(coefs[:, j])),
            "ci95": [
                float(np.percentile(coefs[:, j], 2.5)),
                float(np.percentile(coefs[:, j], 97.5)),
            ],
        }
        for j, n in enumerate(names)
    }


# --- figures -------------------------------------------------------------------------------


def fig_scatter(effects: pd.DataFrame, path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    for ax, (col, label, logx) in zip(
        axes,
        (
            ("age_years_at_break", "Tag age at ChatGPT (years, log scale)", True),
            ("size_2019_2021", "Questions 2019–2021 (log scale)", True),
        ),
        strict=True,
    ):
        x, y = effects[col], effects["pct"]
        ax.scatter(x, y, s=14, color="#0072B2", alpha=0.5, lw=0)
        lx = np.log(x)
        b = np.polyfit(lx, y, 1)
        xs = np.linspace(lx.min(), lx.max(), 50)
        ax.plot(np.exp(xs), np.polyval(b, xs), color="#D55E00", lw=1.8)
        resid = y - np.polyval(b, lx)
        for i in list(resid.nsmallest(4).index) + list(resid.nlargest(4).index):
            ax.annotate(
                effects.loc[i, "tag"],
                (x[i], y[i]),
                fontsize=7,
                color="#555555",
                xytext=(3, 2),
                textcoords="offset points",
            )
        if logx:
            ax.set_xscale("log")
        ax.set_xlabel(label)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#e5e5e5")
    axes[0].set_ylabel("Change vs own pre-2022 trend (%)")
    axes[0].set_title(
        "Older tags fell less (top 297 tags; line = simple fit)", loc="left", fontsize=10
    )
    axes[1].set_title("Bigger tags fell more", loc="left", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_new_tags(new: pd.DataFrame, top_median_pct: float, calib_median: float, path) -> None:
    d = new.dropna(subset=["gap_pct"]).sort_values("gap_pct")
    fig, ax = plt.subplots(figsize=(9, 0.16 * len(d) + 1.5))
    colors = {"new": "#009E73", "version": "#0072B2", "feature": "#CC79A7"}
    for i, r in enumerate(d.itertuples()):
        ax.plot(r.gap_pct, i, "o", color=colors.get(r.kind, "#999999"), ms=4)
    ax.set_yticks(range(len(d)), d["tag"], fontsize=6)
    ax.axvline(top_median_pct, color="#D55E00", lw=1.2, ls="--")
    ax.axvline(d["gap_pct"].median(), color="#333333", lw=1.2)
    ax.axvline(calib_median, color="#999999", lw=1, ls=":")
    ax.set_xlabel("Questions vs lifecycle benchmark (%)")
    ax.set_title(
        "Post-2021 tags vs pre-ChatGPT tags of similar early size\n"
        "solid: new-tag median · dashed: top-300 median · dotted: pre-ChatGPT "
        "calibration median",
        loc="left",
        fontsize=9,
    )
    handles = [plt.Line2D([], [], marker="o", ls="", color=c, label=k) for k, c in colors.items()]
    ax.legend(handles=handles, fontsize=8, frameon=False, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# --- run -----------------------------------------------------------------------------------


def run() -> dict:
    progress.write_manifest(JOB, {"life_counts": 3, "lifecycle": 2, "age": 1, "write": 1})

    def step(name, fn):
        rep = progress.Reporter(JOB, name, 1)
        out = fn()
        rep.finish(1)
        return out

    life = step("life_counts", tag_life_counts)
    retired = T.retired_tags()
    newref = pd.read_csv(config.REFERENCE_DIR / "tags_new_post2021.csv")
    firsts = life.drop_duplicates("tag").set_index("tag")["first_m"]
    newref["first_m"] = newref["tag"].map(firsts)

    def lifecycle():
        targets = newref[~newref["tag"].isin(retired)]
        new = run_lifecycle(life, targets, ("2014-01-01", "2017-11-01"), CUTOFF_MONTH, 60)
        new = new.merge(newref[["tag", "kind", "n_questions"]], on="tag")
        incl = run_lifecycle(life, newref, ("2014-01-01", "2017-11-01"), CUTOFF_MONTH, 60)
        # Calibration before ChatGPT: placebo "new" tags first used 2017-06..2018-11 with
        # >= 200 questions by 2022-11, references first used 2014-01..2016-12.
        pre_end = pd.Timestamp("2022-11-01")
        cand = firsts[(firsts >= "2017-06-01") & (firsts <= "2018-11-01")]
        tot = life[life["tag"].isin(cand.index)]
        months = (
            (pre_end.year - tot["first_m"].dt.year) * 12 + pre_end.month - tot["first_m"].dt.month
        )
        n_by = tot[tot["k"] <= months].groupby("tag")["q"].sum()
        calib_targets = cand[n_by.reindex(cand.index).fillna(0) >= MIN_QUESTIONS]
        calib = run_lifecycle(
            life,
            calib_targets.rename("first_m").reset_index(),
            ("2014-01-01", "2016-12-01"),
            pre_end,
            66,
        )
        return new, incl, calib

    new, new_incl, calib = step("lifecycle", lifecycle)

    def age():
        features = T.load_features()
        draws = pd.read_parquet(config.MODEL_DIR / "tags_negbin_draws.parquet")
        effects = pd.read_csv(TABLES / "tag_effects.csv")
        return features, draws, effects, age_with_pretrend(draws, features)

    features, draws, effects, ctrl = step("age", age)

    def write():
        s = json.loads((QA / "tags_summary.json").read_text())
        g_age = s["effects"]["gamma_per_sd"]["z_log_age"]
        a_supported = g_age["ci95"][1] < 0
        top_tags = [c for c in draws.columns if not c.startswith("__")]
        top_med_draws = np.median(draws[top_tags].to_numpy(), axis=1)  # log, per draw
        rng = np.random.default_rng(SEED)
        g = new["gap_log"].dropna().to_numpy()
        boot_new = np.array([np.median(rng.choice(g, len(g))) for _ in range(B)])
        diff = boot_new - rng.choice(top_med_draws, B)
        b_supported = bool(np.median(g) > np.median(top_med_draws) and np.percentile(diff, 2.5) > 0)
        kinds = new.dropna(subset=["gap_log"]).groupby(
            new["kind"].where(new["kind"] == "new", "version_or_feature")
        )["gap_log"]
        gn = kinds.get_group("new").to_numpy()
        gv = kinds.get_group("version_or_feature").to_numpy()
        kd = np.array(
            [
                np.median(rng.choice(gn, len(gn))) - np.median(rng.choice(gv, len(gv)))
                for _ in range(B)
            ]
        )
        summary = {
            "a_age": {
                "gamma_z_log_age": g_age,
                "supported": bool(a_supported),
                "with_pretrend_control": ctrl,
                "posterior_p_age_ge_0": float(1 - g_age["p_negative"]),
            },
            "b_new_tags": {
                "n_tags": int(new["gap_log"].notna().sum()),
                "n_skipped": int(new["gap_log"].isna().sum()),
                "median_gap_pct": float(T.pct(np.median(g))),
                "median_gap_pct_ci": [
                    float(T.pct(np.percentile(boot_new, 2.5))),
                    float(T.pct(np.percentile(boot_new, 97.5))),
                ],
                "top300_median_pct": float(T.pct(np.median(top_med_draws))),
                "difference_log": float(np.median(diff)),
                "difference_log_ci": [
                    float(np.percentile(diff, 2.5)),
                    float(np.percentile(diff, 97.5)),
                ],
                "one_sided_p_new_not_smaller": float((diff <= 0).mean()),
                "supported": b_supported,
                "including_retired_median_pct": float(T.pct(new_incl["gap_log"].median())),
                "share_new_tags_below_benchmark": float((g < 0).mean()),
            },
            "secondary_kind": {
                "new_median_pct": float(T.pct(np.median(gn))),
                "n_new": len(gn),
                "version_feature_median_pct": float(T.pct(np.median(gv))),
                "n_vf": len(gv),
                "difference_log": float(np.median(kd)),
                "difference_log_ci": [
                    float(np.percentile(kd, 2.5)),
                    float(np.percentile(kd, 97.5)),
                ],
            },
            "calibration_pre_chatgpt": {
                "n_tags": int(calib["gap_log"].notna().sum()),
                "median_gap_pct": float(T.pct(calib["gap_log"].median())),
                "iqr_pct": [
                    float(T.pct(calib["gap_log"].quantile(0.25))),
                    float(T.pct(calib["gap_log"].quantile(0.75))),
                ],
            },
            "h2_supported": bool(a_supported and b_supported),
        }
        new.round(4).to_csv(TABLES / "new_tags_lifecycle.csv", index=False)
        calib.round(4).to_csv(TABLES / "new_tags_lifecycle_calibration.csv", index=False)
        (QA / "thin_data_summary.json").write_text(json.dumps(summary, indent=2, default=float))
        fig_scatter(effects, config.FIGURE_DIR / "tags_age_size_scatter.png")
        fig_new_tags(
            new,
            summary["b_new_tags"]["top300_median_pct"],
            summary["calibration_pre_chatgpt"]["median_gap_pct"],
            config.FIGURE_DIR / "new_tags_lifecycle.png",
        )
        return summary

    return step("write", write)


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=float))
