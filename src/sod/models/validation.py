"""P29: analysis validation - the numbers behind report/validation.md.

1. "Questions not asked": the synthetic-control gap in counts, with an interval from the
   per-month 95% conformal bounds (summing monthly bounds treats months as perfectly
   correlated, so the range is conservative, not an exact 95% interval for the sum), in dump
   terms and with deleted questions included (SEDE).
2. Holm adjustment across the four confirmatory families H2-H5 (pre-registration section 6).
   Each family's decision p-value follows its decision rule: when a rule needs several parts
   to hold, the family p-value is the largest part p-value (intersection-union test); H3's
   "at least 3 of 4" rule uses the third-smallest. Part p-values are one-sided, in the
   predicted direction, from the stored estimates (bootstrap or conformal intervals via a
   normal approximation; posterior tail probabilities for the Bayesian H2 age slope).
3. Leakage checks: the interrupted time series refitted on pre-period weeks only (the joint
   fit lets post-period weeks inform the seasonal and holiday terms).
4. H5 reference-cohort trend: the pre-ChatGPT placebo cohorts themselves drift down, so the
   "below range" rule is compared with a trend extrapolation.

Usage: python -m sod.models.validation
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import stats

from sod import config
from sod.models import its
from sod.models import synth as sc

QA = config.REPORT_DIR / "qa"
TABLES = config.REPORT_DIR / "tables"
ALPHA = 0.05


def _load(name: str) -> dict:
    return json.loads((QA / f"{name}_summary.json").read_text())


# --- 1. questions not asked ------------------------------------------------------------------


def missing_questions(value: str = "questions") -> dict:
    L = sc.load_logs(value=value).loc[: sc.END].dropna(axis=1)
    pre, post = sc.masks(L.index)
    D = sc.demean(L, pre)
    main = sc.synth(D, sc.TREATED, sc.DONORS, pre, post)
    _, ci = sc.pysyncon_fit_and_ci(D, pre, post)
    ci = ci.set_index("period")
    idx = L.index[post]
    so = L.loc[idx, sc.TREATED]
    actual = np.exp(so)
    cf = np.exp(so - main["gap"].loc[idx])
    cf_lo = np.exp(so - ci["upper_ci"].reindex(idx))  # smaller gap -> smaller counterfactual
    cf_hi = np.exp(so - ci["lower_ci"].reindex(idx))
    out = {}
    for name, mask in {
        "all_post": np.ones(len(idx), bool),
        **{str(y): idx.year == y for y in sorted(set(idx.year))},
        "to_2025_09": idx < pd.Timestamp("2025-10-01"),
    }.items():
        out[name] = {
            "actual": float(actual[mask].sum()),
            "counterfactual": float(cf[mask].sum()),
            "missing": float((cf - actual)[mask].sum()),
            "missing_range": [
                float((cf_lo - actual)[mask].sum()),
                float((cf_hi - actual)[mask].sum()),
            ],
            "cumulative_gap_pct": float(100 * (actual[mask].sum() / cf[mask].sum() - 1)),
        }
    return {"att_pct": float(sc.pct(main["att_log"])), "windows": out}


# --- 2. Holm across H2-H5 --------------------------------------------------------------------


def p_from_ci(est: float, lo: float, hi: float, predicted: int, log: bool = False) -> float:
    """One-sided p for 'effect has the predicted sign', normal approximation to a 95% CI."""
    if log:
        est, lo, hi = (np.log1p(v / 100) for v in (est, lo, hi))
    se = (hi - lo) / (2 * 1.96)
    z = predicted * est / se
    return float(stats.norm.sf(z))


def h5_cohort_tests(cohorts: pd.DataFrame) -> dict:
    """H5 2019-21 cohort vs the four pre-ChatGPT reference cohorts (windows ending 2016-2019),
    at distances 2 and 3: (a) level prediction interval (reference mean, t with 3 df);
    (b) trend extrapolation over window end year (t with 2 df); (c) exact rank p (1 of 5)."""
    so = cohorts[cohorts["site"] == config.TREATED]
    out = {}
    for d in (2, 3):
        ref = so[(so["distance"] == d) & so["end"].between(2016, 2019)]
        t = so[(so["distance"] == d) & (so["end"] == 2021)]["share"].iloc[0]
        y, x = ref["share"].to_numpy(), ref["end"].to_numpy().astype(float)
        n = len(y)
        s = y.std(ddof=1)
        level_t = (t - y.mean()) / (s * np.sqrt(1 + 1 / n))
        b, a = np.polyfit(x, y, 1)
        resid = y - (a + b * x)
        s_tr = np.sqrt((resid**2).sum() / (n - 2))
        x0 = 2021.0
        se_pred = s_tr * np.sqrt(1 + 1 / n + (x0 - x.mean()) ** 2 / ((x - x.mean()) ** 2).sum())
        pred = a + b * x0
        out[f"distance_{d}"] = {
            "treated_share": float(t),
            "reference_shares": [float(v) for v in y],
            "reference_trend_per_year": float(b),
            "level": {"expected": float(y.mean()), "p": float(stats.t.cdf(level_t, n - 1))},
            "trend": {
                "expected": float(pred),
                "shortfall": float(t - pred),
                "p": float(stats.t.cdf((t - pred) / se_pred, n - 2)),
            },
            "rank_p": float((np.sum(y <= t) + 1) / (n + 1)),
        }
    return out


def holm(pvals: dict[str, float], alpha: float = ALPHA) -> dict:
    order = sorted(pvals, key=pvals.get)
    k = len(order)
    out, still = {}, True
    running = 0.0
    for i, h in enumerate(order):
        adj = min(1.0, max(running, (k - i) * pvals[h]))
        running = adj
        reject = still and pvals[h] <= alpha / (k - i)
        still = reject
        out[h] = {
            "p": pvals[h],
            "holm_threshold": alpha / (k - i),
            "holm_adjusted_p": adj,
            "reject": bool(reject),
        }
    return out


def family_pvalues() -> dict:
    td, qm, nc, an = (_load(n) for n in ("thin_data", "question_mix", "newcomers", "answerers"))
    parts: dict[str, dict] = {}
    # H2: (a) age slope negative (posterior tail), (b) new tags decline less (bootstrap)
    parts["H2"] = {
        "a_age_slope_negative": 1 - td["a_age"]["gamma_z_log_age"]["p_negative"],
        "b_new_tags_smaller_decline": max(
            td["b_new_tags"]["one_sided_p_new_not_smaller"], 1 / 4000
        ),
    }
    # H3: within-tag change in predicted direction, per measure; rule = at least 3 of 4
    h3 = {
        m["measure"]: p_from_ci(m["within"], *m["within_ci"], predicted=m["predicted"])
        for m in qm["measures"]
        if m["measure"] in ("body_length", "code_share", "dup_share", "first_time_share")
    }
    parts["H3"] = h3
    # H4: (a) log share of first-time askers falls (conformal interval), (b) return lower at
    # 91 and 365 days (Greenwood)
    a = nc["a_synth"]["log_share_first_time"]
    parts["H4"] = {
        "a_first_time_share_falls": p_from_ci(a["att_pct"], *a["ci_pct"], predicted=-1, log=True),
        **{
            f"b_return_{h}d_lower": p_from_ci(
                nc["b_km"]["2023-2026"][h]["diff_vs_2019_2021"],
                *nc["b_km"]["2023-2026"][h]["diff_ci"],
                predicted=-1,
            )
            for h in ("91", "365")
        },
    }
    cohorts = pd.read_csv(TABLES / "answerer_cohorts.csv")
    h5 = h5_cohort_tests(cohorts)
    parts["H5"] = {
        f"{k}_{v}": h5[k][v]["p"] for k in ("distance_2", "distance_3") for v in ("level",)
    }
    family = {
        "H2": max(parts["H2"].values()),
        "H3": sorted(parts["H3"].values())[2],
        "H4": max(parts["H4"].values()),
        "H5": max(parts["H5"].values()),
    }
    # H5 alternatives (the decision rule itself is a range comparison, which has no p-value)
    h5_alt = {
        "trend_extrapolation": max(h5[k]["trend"]["p"] for k in ("distance_2", "distance_3")),
        "exact_rank": max(h5[k]["rank_p"] for k in ("distance_2", "distance_3")),
    }
    return {
        "parts": parts,
        "family_p": family,
        "holm": holm(family),
        "h5_cohorts": h5,
        "h5_alternative_family_p": h5_alt,
        "holm_with_h5_trend": holm({**family, "H5": h5_alt["trend_extrapolation"]}),
    }


# --- 3. leakage: ITS fitted on pre-period weeks only -----------------------------------------


def its_pre_only() -> dict:
    y = its.load_weekly()
    out = {}
    for name, start in its.STARTS.items():
        s = pd.Timestamp(start)
        model, X, yy = its.fit(y, start, end=its.BREAK - pd.Timedelta(days=1))
        smear = float(np.exp(model.resid).mean())
        yp = y.loc[its.BREAK :]
        Xp = its.design(yp.index, s)[X.columns]
        gap = np.log(yp.to_numpy()) - Xp.to_numpy() @ model.params.to_numpy()
        cf = np.exp(Xp.to_numpy() @ model.params.to_numpy()) * smear
        joint = _load("its")["fits"][name]["windows"]["all_post"]
        out[name] = {
            "pre_only_mean_gap_pct": float(its._pct(gap.mean())),
            "pre_only_cumulative_gap_pct": float(100 * (yp.sum() / cf.sum() - 1)),
            "joint_fit_mean_gap_pct": joint["mean_gap_pct"],
            "joint_fit_cumulative_gap_pct": joint["cumulative_gap_pct"],
        }
    return out


def run() -> dict:
    summary = {
        "missing_questions": missing_questions("questions"),
        "missing_questions_incl_deleted": missing_questions("questions_incl_deleted"),
        "multiplicity": family_pvalues(),
        "its_pre_only": its_pre_only(),
    }
    (QA / "validation_summary.json").write_text(json.dumps(summary, indent=2, default=float))
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=float))
