"""P30: every number quoted in report/index.qmd, read from the model summaries.

The article never types a result by hand: it shows `N["key"]` values built here, so a rerun
of the pipeline updates the text, and tests/test_article.py checks the keys.
"""

from __future__ import annotations

import json
from functools import cache

from sod import config

MINUS = "−"


def _load(name: str) -> dict:
    return json.loads((config.REPORT_DIR / "qa" / f"{name}_summary.json").read_text())


def pct(x: float, digits: int = 0, sign: bool = True) -> str:
    """-72.31 -> '−72%', 18.3 -> '+18%'; sign=False drops the sign (for 'fell 72%')."""
    if x is None or x != x:  # e.g. an empty constant-effect interval
        return "n/a"
    v = abs(x) if not sign else x
    s = f"{v:.{digits}f}%"
    if not sign:
        return s
    return ("+" + s if v > 0 else s).replace("-", MINUS)


def signed_pct(x: float, digits: int = 0) -> str:
    """Explicit sign: +18%, −72% (same as pct; kept for readability at call sites)."""
    return pct(x, digits)


def share(x: float, digits: int = 0) -> str:
    return f"{100 * x:.{digits}f}%"


def millions(x: float, digits: int = 1) -> str:
    return f"{x / 1e6:.{digits}f} million"


def interval(lo: float, hi: float, fmt=pct, **kw) -> str:
    return f"{fmt(lo, **kw)} to {fmt(hi, **kw)}"


@cache
def numbers() -> dict[str, str]:
    s, its, fc, rob = (_load(n) for n in ("synth", "its", "forecast", "robustness"))
    td, qm, nc, an = (_load(n) for n in ("thin_data", "question_mix", "newcomers", "answerers"))
    rs, gh, v = (_load(n) for n in ("responsiveness", "github", "validation"))
    tags = _load("tags")
    att = s["att"]
    mon = s["att_interval_readings_pct"]["monthly_average"]
    miss = v["missing_questions"]["windows"]
    miss_d = v["missing_questions_incl_deleted"]["windows"]["all_post"]
    pw = s["platform_wide"]
    its_f = its["fits"]
    r3 = an["distance3_ratio_2019_21_vs_reference_mean"]
    n: dict[str, str] = {
        # H1
        "att": pct(att["all_post"]["att_pct"]),
        "att_abs": pct(att["all_post"]["att_pct"], sign=False),
        "att_ci": interval(*mon),
        "att_const_ci": interval(*s["att_interval_readings_pct"]["constant_effect"]),
        "months_excl_zero": str(s["months_interval_excludes_zero"]),
        "months_post": str(att["all_post"]["months"]),
        "rank": f"{s['placebo_space']['so_rank']} of {s['placebo_space']['n']}",
        "p_space": f"{s['placebo_space']['p_value']:.4f}".rstrip("0"),
        "pre_rmspe": f"{s['pre_rmspe']:.3f}",
        "time_placebos": interval(
            min(r["att_pct"] for r in s["placebo_time"]),
            max(r["att_pct"] for r in s["placebo_time"]),
            fmt=signed_pct,
        ),
        **{f"att_{y}": pct(att[y]["att_pct"]) for y in ("2023", "2024", "2025", "2026")},
        "att_to_2025_09": pct(att["to_2025_09"]["att_pct"]),
        "missing": millions(miss["all_post"]["missing"]),
        "missing_range": f"{miss['all_post']['missing_range'][0] / 1e6:.1f}–"
        f"{miss['all_post']['missing_range'][1] / 1e6:.1f} million",
        "missing_deleted": millions(miss_d["missing"]),
        "missing_deleted_range": f"{miss_d['missing_range'][0] / 1e6:.1f}–"
        f"{miss_d['missing_range'][1] / 1e6:.1f} million",
        "cum_gap": pct(miss["all_post"]["cumulative_gap_pct"]),
        "actual_post": millions(miss["all_post"]["actual"], 2),
        "cf_post": millions(miss["all_post"]["counterfactual"], 2),
        # supporting estimators and robustness
        "its": pct(its_f["preregistered"]["windows"]["all_post"]["mean_gap_pct"]),
        "its_covid": pct(its_f["post_covid"]["windows"]["all_post"]["mean_gap_pct"]),
        "its_holdout": interval(
            its_f["preregistered"]["holdout_2021_12_to_2022_11"]["mean_error_pct"],
            its_f["post_covid"]["holdout_2021_12_to_2022_11"]["mean_error_pct"],
        ),
        "its_level": pct(its_f["preregistered"]["post"]["pct"]),
        "its_slope": pct(its_f["preregistered"]["post_slope"]["pct"]),
        "ets": pct(fc["models"]["ets"]["gaps"]["all_post"]["mean_gap_pct"]),
        "prophet": pct(fc["models"]["prophet"]["gaps"]["all_post"]["mean_gap_pct"]),
        "ets_bt": ", ".join(
            pct(x)
            for x in fc["models"]["ets"]["backtest"]["mean_error_pct_by_horizon_year"].values()
        ),
        "prophet_bt": ", ".join(
            pct(x)
            for x in fc["models"]["prophet"]["backtest"]["mean_error_pct_by_horizon_year"].values()
        ),
        "rob_range": interval(*sorted(rob["att_range_pct"])),
        "att_deleted": pct(v["missing_questions_incl_deleted"]["att_pct"]),
        "n_variants": str(rob["n_variants"]),
        "did_ru": pct(s["did_ru"]["did_pct"]),
        "did_ru_ci": interval(*s["did_ru"]["did_pct_ci"]),
        # programming-specific
        "donor_gap": pct(pw["median_donor_gap_pct"]),
        "so_own_gap": pct(pw["so_gap_pct"]),
        "donor_ratio": f"{pw['ratio_donor_to_so']:.2f}",
        # H2
        "n_tags": str(tags["n_tags"]),
        "age_slope": f"+{td['a_age']['gamma_z_log_age']['median']:.2f}",
        "age_slope_ci": "+{:.2f} to +{:.2f}".format(*td["a_age"]["gamma_z_log_age"]["ci95"]),
        "new_tags_n": str(td["b_new_tags"]["n_tags"]),
        "new_tags_gap": pct(td["b_new_tags"]["median_gap_pct"]),
        "new_tags_ci": interval(*td["b_new_tags"]["median_gap_pct_ci"]),
        "top300_gap": pct(td["b_new_tags"]["top300_median_pct"]),
        "new_kind": pct(td["secondary_kind"]["new_median_pct"]),
        "vf_kind": pct(td["secondary_kind"]["version_feature_median_pct"]),
        "calib": pct(td["calibration_pre_chatgpt"]["median_gap_pct"]),
        "tag_rank_rho": f"{v['tag_rank_check']['spearman_all']:.1f}",
        "tag_raw_p10": pct(v["tag_rank_check"]["raw_pct_quantiles"]["0.1"]),
        "tag_raw_p90": pct(v["tag_rank_check"]["raw_pct_quantiles"]["0.9"]),
        # H3
        **_h3(qm),
        # H4
        "ft_share_att": signed_pct(nc["a_synth"]["log_share_first_time"]["att_pct"]),
        "ft_share_ci": interval(*nc["a_synth"]["log_share_first_time"]["ci_pct"]),
        "ft_askers_att": pct(nc["a_synth"]["first_time_askers"]["att_pct"]),
        "ret12_before": share(nc["b_km"]["2019-2021"]["365"]["p"], 1),
        "ret12_after": share(nc["b_km"]["2023-2026"]["365"]["p"], 1),
        "ret12_sg": share(nc["b_km"]["2024-06..2026-09 (Staging Ground)"]["365"]["p"], 1),
        "ret3_before": share(nc["b_km"]["2019-2021"]["91"]["p"], 1),
        "ret3_after": share(nc["b_km"]["2023-2026"]["91"]["p"], 1),
        # H5
        "core_d2": share(an["h5_test"]["distance_2"]["treated_share"], 1),
        "core_d3": share(an["h5_test"]["distance_3"]["treated_share"], 1),
        "ref_d2": interval(
            an["h5_test"]["distance_2"]["reference_min"],
            an["h5_test"]["distance_2"]["reference_max"],
            fmt=share,
            digits=1,
        ),
        "ref_d3": interval(
            an["h5_test"]["distance_3"]["reference_min"],
            an["h5_test"]["distance_3"]["reference_max"],
            fmt=share,
            digits=1,
        ),
        "h5_p": f"{v['multiplicity']['family_p']['H5']:.3f}",
        "h5_holm_p": f"{v['multiplicity']['holm']['H5']['holm_adjusted_p']:.3f}",
        "h5_trend_exp_d3": share(
            v["multiplicity"]["h5_cohorts"]["distance_3"]["trend"]["expected"], 1
        ),
        "h5_trend_exp_d2": share(
            v["multiplicity"]["h5_cohorts"]["distance_2"]["trend"]["expected"], 1
        ),
        "core_ratio_so": f"{r3['stackoverflow']:.2f}",
        "core_ratio_donor": f"{r3['donor_median']:.2f}",
        # E1
        "a24_before": share(rs["by_group_and_period"]["treated"]["rate_answered_24h"]["2019-2021"]),
        "a24_2025": share(rs["by_group_and_period"]["treated"]["rate_answered_24h"]["2025"]),
        "speed_2019": f"{rs['so_median_hours_if_answered_7d_by_year']['2019']:.1f}",
        "speed_2025": f"{rs['so_median_hours_if_answered_7d_by_year']['2025']:.1f}",
        "old_q_2019": share(_answer_age(rs, 2019), 0),
        "old_q_2025": share(_answer_age(rs, 2025), 0),
        # E2
        "gh_index": f"{gh['median_gh_index']['2025h1']:.0f}",
        "so_tag_index": f"{gh['median_so_index']['2025h1']:.0f}",
        "gh_all_index": f"{gh['all_github_issue_events_index_median']['2025h1']:.0f}",
        "gh_pairs": str(gh["pairs"]),
        **{
            f"ai_use_{r['year']}": f"{r['using_pct']:.0f}%"
            for r in gh["so_survey_ai_use"]
            if r["using_pct"] is not None and r["using_pct"] == r["using_pct"]  # skip NaN
        },
    }
    return {k: ("n/a" if "nan" in v.lower() else v) for k, v in n.items()}  # undefined values


def _h3(qm: dict) -> dict[str, str]:
    m = {x["measure"]: x for x in qm["measures"]}
    b, c, d, f = (m[k] for k in ("body_length", "code_share", "dup_share", "first_time_share"))
    return {
        "body_2021": f"{b['y2021']:,.0f}",
        "body_2025": f"{b['y2025']:,.0f}",
        "body_within": f"+{b['within']:,.0f}",
        "body_lee": "+{:,.0f} to +{:,.0f}".format(*b["within_lee_bounds"]),
        "code_within": f"+{100 * c['within']:.1f}",
        "dup_2021": share(d["y2021"], 1),
        "dup_2025": share(d["y2025"], 1),
        "ft_2021": share(f["y2021"], 1),
        "ft_2025": share(f["y2025"], 1),
        "acct_age_2021": f"{m['account_age']['y2021']:,.0f}",
        "acct_age_2025": f"{m['account_age']['y2025']:,.0f}",
    }


def _answer_age(rs: dict, year: int) -> float:
    row = next(r for r in rs["answer_age_by_year"] if r["year"] == year)
    return row["to_questions_over_1y"]
