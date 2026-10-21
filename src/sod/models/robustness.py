"""P18: pre-registered robustness checks (PREREGISTRATION.md section 7) and a forest plot.

Every synthetic-control variant reports: the average post-period gap (ATT, %), the average of
the per-month 95% conformal bounds (deviation 2026-10-21), the placebo-in-space rank among the
16 sites, the pre-fit rule, and whether the H1 verdict holds (ATT <= -10%, interval excludes 0,
rank 1). Supporting estimators (P15, P16) are read from their saved summaries.

Checks: 1 alternative breaks (Copilot GA 2022-06, GPT-4 2023-03); 2 strike months excluded;
3 pre-period from 2014; 4 weekly; 5 donor pools (no math, leave-one-out, tech added);
6 augmented SC (ridge, point estimate only); 7 post-period to 2025-09; 8 deleted posts included
(SEDE counts for all sites); 9 answers and new posters as outcomes; 10 November 2022 dropped.

Progress: `make progress` (job "robustness").

Usage: python -m sod.models.robustness
"""

from __future__ import annotations

import json
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from sod import config, progress  # noqa: E402
from sod.models import synth as sc  # noqa: E402

JOB = "robustness"
QA = config.REPO_ROOT / "report" / "qa"
TABLES = config.REPO_ROOT / "report" / "tables"
STRIKE = (pd.Timestamp("2023-06-01"), pd.Timestamp("2023-08-01"))
WEEK_COVID = (pd.Timestamp("2020-03-09"), pd.Timestamp("2020-06-29"))  # weeks overlapping


def make_masks(index, pre_end, post_end=None, exclude_post=None, exclude_pre=None, weekly=False):
    lo, hi = WEEK_COVID if weekly else sc.COVID
    cov = np.asarray((index >= lo) & (index <= hi))
    pre = np.asarray(index <= pd.Timestamp(pre_end)) & ~cov
    post = np.asarray(index > pd.Timestamp(pre_end)) & ~cov
    if post_end is not None:
        post &= np.asarray(index <= pd.Timestamp(post_end))
    for mask, excl in ((post, exclude_post), (pre, exclude_pre)):
        if excl is not None:
            mask &= ~np.asarray((index >= excl[0]) & (index <= excl[1]))
    return pre, post


def estimate(L, pre, post, donors=sc.DONORS, with_ci=True) -> dict:
    D = sc.demean(L[[sc.TREATED, *donors]], pre)
    main = sc.synth(D, sc.TREATED, donors, pre, post)
    ps = sc.placebo_space(D, pre, post, donors=donors)
    so = ps[ps["site"] == sc.TREATED].iloc[0]
    donor_pre = ps[ps["site"] != sc.TREATED]["pre_rmspe"]
    out = {
        "att_pct": float(sc.pct(main["att_log"])),
        "pre_rmspe": main["pre_rmspe"],
        "prefit_ok": bool(main["pre_rmspe"] <= 2 * donor_pre.median()),
        "rank": int(so["rank"]),
        "n_units": len(ps),
        "low": np.nan,
        "high": np.nan,
        "top_weights": ", ".join(
            f"{k.split('.')[0]} {v:.2f}"
            for k, v in sorted(main["weights"].items(), key=lambda kv: -kv[1])
            if v >= 0.1
        ),
    }
    if with_ci:
        _, ci = sc.pysyncon_fit_and_ci(D, pre, post, donors=donors)
        out["low"] = float(sc.pct(ci["lower_ci"].mean()))
        out["high"] = float(sc.pct(ci["upper_ci"].mean()))
        out["share_months_excl_zero"] = float((ci["upper_ci"] < 0).mean())
    return out


def augsynth(L, pre, post) -> dict:
    from pysyncon import AugSynth, Dataprep

    D = sc.demean(L[[sc.TREATED, *sc.DONORS]], pre)
    # AugSynth needs one unbroken pre-period: drop the excluded (COVID) months and renumber.
    keep = pre | post
    D, pre, post = D[keep], pre[keep], post[keep]
    long = D.reset_index(names="period").melt(id_vars="period", var_name="site", value_name="y")
    t = {p: i for i, p in enumerate(D.index)}
    long["t"] = long["period"].map(t)
    pre_t = [t[p] for p in D.index[pre]]
    post_t = [t[p] for p in D.index[post]]
    dp = Dataprep(
        foo=long,
        predictors=["y"],
        predictors_op="mean",
        dependent="y",
        unit_variable="site",
        time_variable="t",
        treatment_identifier=sc.TREATED,
        controls_identifier=sc.DONORS,
        time_predictors_prior=pre_t,
        time_optimize_ssr=pre_t,
    )
    a = AugSynth()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        a.fit(dataprep=dp)
        att = a.att(time_period=post_t)
    return {
        "att_pct": float(sc.pct(att["att"])),
        "low": np.nan,
        "high": np.nan,
        "lambda": float(a.lambda_) if getattr(a, "lambda_", None) is not None else None,
    }


def h1_holds(r: dict) -> bool | None:
    if np.isnan(r.get("high", np.nan)):
        return None
    return bool(r["att_pct"] <= -10 and r["high"] < 0 and r.get("rank", 1) == 1)


def variants():
    """(id, group, label, callable returning a result dict)."""
    L = sc.load_logs(start=sc.START).loc[: sc.END]
    pe = sc.PRE_END
    yield (
        "0",
        "Primary",
        "Primary: synthetic control, 15 donors",
        lambda: estimate(L, *make_masks(L.index, pe)),
    )
    yield (
        "1a",
        "1 Break date",
        "Break at Copilot GA (2022-06)",
        lambda: estimate(L, *make_masks(L.index, "2022-05-01")),
    )
    yield (
        "1b",
        "1 Break date",
        "Break at GPT-4 (2023-03)",
        lambda: estimate(L, *make_masks(L.index, "2023-02-01")),
    )
    yield (
        "2",
        "2 Strike",
        "Strike months (2023-06..08) excluded",
        lambda: estimate(L, *make_masks(L.index, pe, exclude_post=STRIKE)),
    )

    def from_2014():
        L14 = sc.load_logs(start="2014-01-01").loc[: sc.END]
        return estimate(L14, *make_masks(L14.index, pe))

    yield "3", "3 Pre-period", "Pre-period from 2014-01", from_2014

    def weekly():
        W = sc.load_logs(start="2017-01-02", panel="site_week")
        return estimate(W, *make_masks(W.index, "2022-11-21", weekly=True))

    yield "4", "4 Weekly", "Weekly data", weekly
    no_math = [d for d in sc.DONORS if d != sc.MATH]
    yield (
        "5a",
        "5 Donors",
        "Without Mathematics",
        lambda: estimate(L, *make_masks(L.index, pe), donors=no_math),
    )

    def loo():
        pre, post = make_masks(L.index, pe)
        atts = []
        for d in sc.DONORS:
            pool = [x for x in sc.DONORS if x != d]
            r = sc.synth(sc.demean(L[[sc.TREATED, *pool]], pre), sc.TREATED, pool, pre, post)
            atts.append(float(sc.pct(r["att_log"])))
        return {
            "att_pct": float(np.median(atts)),
            "low": min(atts),
            "high": max(atts),
            "range_not_ci": True,
        }

    yield "5b", "5 Donors", "Leave one donor out (median; bar = range)", loo
    yield (
        "5c",
        "5 Donors",
        "Tech sites added as donors (21)",
        lambda: estimate(L, *make_masks(L.index, pe), donors=sc.DONORS + sc.TECH),
    )
    yield (
        "6",
        "6 Augmented",
        "Augmented synthetic control (ridge)",
        lambda: augsynth(L, *make_masks(L.index, pe)),
    )
    yield (
        "7",
        "7 Late period",
        "Post-period ends 2025-09",
        lambda: estimate(L, *make_masks(L.index, pe, post_end="2025-09-01")),
    )

    def deleted():
        Ld = sc.load_logs(value="questions_incl_deleted").loc[: sc.END]
        return estimate(Ld, *make_masks(Ld.index, pe))

    yield "8", "8 Deleted posts", "Deleted questions included (SEDE)", deleted
    for value, label in (("answers", "Outcome: answers"), ("new_posters", "Outcome: new posters")):

        def outcome(value=value):
            Lo = sc.load_logs(value=value).loc[: sc.END]
            return estimate(Lo, *make_masks(Lo.index, pe))

        yield f"9{value[0]}", "9 Outcomes", label, outcome
    yield (
        "10",
        "10 Nov 2022",
        "November 2022 dropped from pre-period",
        lambda: estimate(L, *make_masks(L.index, pe, exclude_pre=(pe, pe))),
    )


def supporting() -> list[dict]:
    rows = []
    its = json.loads((QA / "its_summary.json").read_text())["fits"]
    for name, label in (
        ("preregistered", "ITS, trend from 2017 (weekly)"),
        ("post_covid", "ITS, trend from 2020-07 (exploratory)"),
    ):
        w = its[name]["windows"]["all_post"]
        rows.append(
            {
                "id": f"S-its-{name}",
                "group": "Supporting",
                "label": label,
                "att_pct": w["mean_gap_pct"],
                "low": w["mean_gap_pct_ci"][0],
                "high": w["mean_gap_pct_ci"][1],
            }
        )
    fc = json.loads((QA / "forecast_summary.json").read_text())["models"]
    for name, label in (("ets", "Forecast: ETS"), ("prophet", "Forecast: Prophet")):
        g = fc[name]["gaps"]["all_post"]
        rows.append(
            {
                "id": f"S-{name}",
                "group": "Supporting",
                "label": label,
                "att_pct": g["mean_gap_pct"],
                "low": g["mean_gap_pct_ci"][0],
                "high": g["mean_gap_pct_ci"][1],
            }
        )
    return rows


def fig_forest(df: pd.DataFrame, path) -> None:
    d = df.iloc[::-1].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(10, 0.36 * len(d) + 1.4))
    y = np.arange(len(d))
    primary = d.loc[d["id"] == "0", "att_pct"].iloc[0]
    ax.axvspan(-10, 0, color="#eeeeee", lw=0)
    ax.axvline(0, color="#999999", lw=0.8)
    ax.axvline(primary, color="#D55E00", lw=0.8, ls=":")
    for i, r in d.iterrows():
        sup = r["group"] == "Supporting"
        c = "#555555" if sup else ("#D55E00" if r["id"] == "0" else "#0072B2")
        if not np.isnan(r["low"]):
            ax.plot(
                [r["low"], r["high"]],
                [i, i],
                color=c,
                lw=1.6,
                ls=":" if r.get("range_not_ci") is True else "-",
            )
        ax.plot(r["att_pct"], i, "s" if sup else "o", color=c, ms=6)
        ax.text(1.5, i, f"{r['att_pct']:.0f}%", va="center", fontsize=8, color="#333333")
    ax.set_yticks(y, d["label"], fontsize=8)
    ax.set_xlim(-100, 8)
    ax.set_xlabel("Average post-period gap vs counterfactual (%, 95% interval)")
    ax.set_title(
        "Robustness: every pre-registered variant of the headline estimate", loc="left", fontsize=11
    )
    ax.text(
        -9.5, -0.9, "smaller than the\n−10% threshold", fontsize=7, color="#777777", va="bottom"
    )
    ax.set_ylim(-1.2, len(d) - 0.5)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def run() -> pd.DataFrame:
    specs = list(variants())
    progress.write_manifest(JOB, {"variants": len(specs)})
    rep = progress.Reporter(JOB, "variants", len(specs))
    rows = []
    try:
        for i, (vid, group, label, fn) in enumerate(specs, start=1):
            r = fn()
            rows.append({"id": vid, "group": group, "label": label, **r})
            rep._last = 0
            rep.update(i, i)
    except BaseException:
        rep.finish(0, status="failed")
        raise
    rep.finish(len(rows))
    df = pd.DataFrame(rows + supporting())
    df["h1_holds"] = [h1_holds(r) for r in df.to_dict(orient="records")]
    df.loc[df["group"] == "Supporting", "h1_holds"] = None
    df.loc[df["id"] == "5b", "h1_holds"] = None  # a range, not an interval
    TABLES.mkdir(parents=True, exist_ok=True)
    df.round(4).to_csv(TABLES / "robustness.csv", index=False)
    flips = df[(df["h1_holds"] == False) & (df["group"] != "Supporting")]  # noqa: E712
    summary = {
        "n_variants": int((df["group"] != "Supporting").sum()),
        "att_range_pct": [float(df["att_pct"].min()), float(df["att_pct"].max())],
        "h1_flips": flips[["id", "label"]].to_dict(orient="records"),
        "prefit_failures": df.loc[df.get("prefit_ok") == False, "label"].tolist(),  # noqa: E712
    }
    (QA / "robustness_summary.json").write_text(json.dumps(summary, indent=2))
    fig_forest(df, config.FIGURE_DIR / "robustness_forest.png")
    return df


if __name__ == "__main__":
    out = run()
    cols = [
        "id",
        "label",
        "att_pct",
        "low",
        "high",
        "rank",
        "pre_rmspe",
        "prefit_ok",
        "share_months_excl_zero",
        "h1_holds",
        "top_weights",
    ]
    with pd.option_context("display.width", 250, "display.max_colwidth", 60):
        print(out[[c for c in cols if c in out]].round(2).to_string(index=False))
