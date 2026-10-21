"""P19: tag-level effects for the top 300 Stack Overflow tags (H2; PREREGISTRATION.md section 6
and deviation 2026-10-21 "H2 per-tag outcome modelled as counts").

Hierarchical negative binomial on monthly question counts, 2017-01..2026-09 (each tag's series
starts at the later of 2017-01 and six months after its first question):

  log mu[t,m] = offset[t] + a[t] + b[t] * years[m] + season[month] + covid * covid[m]
                + post[m] * (delta[t] + kappa[t] * (years_since_break[m] - mean_post_years))
  delta[t]    = g0 + g_age * z_log_age + g_size * z_log_size + g_dup * z_dup_share
                + family[f(t)] + sigma_delta * eps[t]                      (partial pooling)
  kappa[t]    = k0 + sigma_kappa * eps2[t]
  y[t,m]      ~ NegativeBinomial(mu, alpha[t]),  log alpha[t] hierarchical

Each tag gets its own post-ChatGPT line, so its pre-trend b[t] is learned from pre-period months
only (a single level term let the steepening post-period decline pull the pre-trend down; found
in a 30-tag smoke test, see PREREGISTRATION.md deviations). The line is centred at the middle
of the post-period, so delta[t] is the tag's average log gap against its own extended pre-trend,
the same measure as the headline synthetic-control estimate; exp(delta) - 1 is reported.
The "original" pre-registered version (log(count + 1), normal likelihood, same structure) is
fitted as a sensitivity check.

Shrinkage diagnostics compare the pooled estimates with unpooled per-tag Poisson GLMs.

Progress: `make progress` (job "tags"; the sampling steps jump when each model finishes).

Usage: python -m sod.models.tags
"""

from __future__ import annotations

import json
import time
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.api as sm  # noqa: E402

from sod import config, progress  # noqa: E402

JOB = "tags"
START = pd.Timestamp("2017-01-01")
PRE_END = pd.Timestamp("2022-11-01")
END = pd.Timestamp("2026-09-01")
COVID = (pd.Timestamp("2020-03-01"), pd.Timestamp("2020-06-01"))
CENTRE = pd.Timestamp("2020-01-01")
RAMP_MONTHS = 6
DRAWS, TUNE, CHAINS, SEED = 1000, 1000, 4, 20261021
QA = config.REPO_ROOT / "report" / "qa"
TABLES = config.REPO_ROOT / "report" / "tables"
PREDICTORS = ["z_log_age", "z_log_size", "z_dup_share"]


# --- data ------------------------------------------------------------------------------


RETIRE_MIN_MEAN, RETIRE_SHARE, RETIRE_WINDOW = 20, 0.05, 6


def retired(q: pd.Series) -> pd.Timestamp | None:
    """First month of an abrupt retirement (deviation 2026-10-21): the previous 6 months
    average >= 20 questions and each of the next 6 months is below 5% of that average."""
    v = q.sort_index().to_numpy(dtype=float)
    w = RETIRE_WINDOW
    for i in range(w, len(v) - w + 1):
        prev = v[i - w : i].mean()
        if prev >= RETIRE_MIN_MEAN and v[i : i + w].max() < RETIRE_SHARE * prev:
            return q.sort_index().index[i]
    return None


def retired_tags(groups=("top300", "new_post2021")) -> dict[str, pd.Timestamp]:
    t = pd.read_parquet(config.PANEL_DIR / "tag_month.parquet")
    t = t[t["tag_group"].isin(groups) & ~t["partial_period"]]
    out = {}
    for tag, g in t.groupby("tag"):
        when = retired(g.set_index("period")["questions"])
        if when is not None:
            out[tag] = when
    return out


def load_features(exclude_retired: bool = True) -> pd.DataFrame:
    f = pd.read_csv(config.REFERENCE_DIR / "tag_features.csv", parse_dates=["first_seen"])
    if exclude_retired:
        f = f[~f["tag"].isin(retired_tags(("top300",)))]
    f["log_age"] = np.log(f["age_years_at_break"])
    f["log_size"] = np.log(f["size_2019_2021"])
    for src, z in (
        ("log_age", "z_log_age"),
        ("log_size", "z_log_size"),
        ("dup_share_2019_2021", "z_dup_share"),
    ):
        f[z] = (f[src] - f[src].mean()) / f[src].std()
    return f.reset_index(drop=True)


def load_panel(features: pd.DataFrame) -> pd.DataFrame:
    t = pd.read_parquet(config.PANEL_DIR / "tag_month.parquet")
    t = t[(t["tag_group"] == "top300") & ~t["partial_period"]]
    t = t[(t["period"] >= START) & (t["period"] <= END)]
    first = features.set_index("tag")["first_seen"].dt.to_period("M").dt.to_timestamp()
    start = (first + pd.DateOffset(months=RAMP_MONTHS)).clip(lower=START)
    t = t[t["period"] >= t["tag"].map(start)]
    t = t.merge(features[["tag", "family"]], on="tag")
    t["tag_idx"] = t["tag"].map({tag: i for i, tag in enumerate(features["tag"])})
    t["years"] = (t["period"] - CENTRE).dt.days / 365.25
    t["month"] = t["period"].dt.month - 1
    t["covid"] = t["period"].between(*COVID).astype(float)
    t["post"] = (t["period"] > PRE_END).astype(float)
    since = (t["period"] - PRE_END).dt.days / 365.25
    post_mean = since[t["post"] == 1].groupby(t["period"]).first().mean()
    t["post_slope"] = t["post"] * (since - post_mean)
    return t.sort_values(["tag_idx", "period"]).reset_index(drop=True)


def offsets(panel: pd.DataFrame, n_tags: int) -> np.ndarray:
    pre = panel[(panel["post"] == 0) & (panel["covid"] == 0)]
    m = pre.groupby("tag_idx")["questions"].mean().reindex(range(n_tags))
    return np.log(m.clip(lower=0.5)).to_numpy()


# --- model -----------------------------------------------------------------------------


def build_model(panel: pd.DataFrame, features: pd.DataFrame, likelihood: str = "negbin"):
    import pymc as pm

    n_tags = len(features)
    families = sorted(features["family"].unique())
    fam_idx = features["family"].map({f: i for i, f in enumerate(families)}).to_numpy()
    Z = features[PREDICTORS].to_numpy()
    tag = panel["tag_idx"].to_numpy()
    off = offsets(panel, n_tags) if likelihood == "negbin" else log1p_offset_fix(panel, n_tags)
    y = panel["questions"].to_numpy()
    coords = {
        "tag": features["tag"].tolist(),
        "family": families,
        "predictor": PREDICTORS,
        "month": list("JFMAMJJASOND"),
    }
    with pm.Model(coords=coords) as model:
        sigma_a = pm.HalfNormal("sigma_a", 1.0)
        # Centred parameterisation: every top-300 tag has thousands of questions, so the data
        # dominate each tag's parameters (non-centred mixed poorly in the first full run).
        a = pm.Normal("a", 0, sigma_a, dims="tag")
        beta0 = pm.Normal("beta0", 0, 0.5)
        sigma_b = pm.HalfNormal("sigma_b", 0.5)
        b = pm.Normal("b", beta0, sigma_b, dims="tag")
        season = pm.ZeroSumNormal("season", sigma=0.3, dims="month")
        covid = pm.Normal("covid", 0, 0.5)
        g0 = pm.Normal("g0", 0, 1.5)
        gamma = pm.Normal("gamma", 0, 0.5, dims="predictor")
        sigma_f = pm.HalfNormal("sigma_family", 0.5)
        fam = pm.Deterministic(
            "family_effect", sigma_f * pm.Normal("family_z", 0, 1, dims="family"), dims="family"
        )
        sigma_d = pm.HalfNormal("sigma_delta", 1.0)
        delta = pm.Normal("delta", g0 + pm.math.dot(Z, gamma) + fam[fam_idx], sigma_d, dims="tag")
        k0 = pm.Normal("k0", 0, 1.0)
        sigma_k = pm.HalfNormal("sigma_kappa", 0.5)
        kappa = pm.Normal("kappa", k0, sigma_k, dims="tag")
        eta = (
            off[tag]
            + a[tag]
            + b[tag] * panel["years"].to_numpy()
            + season[panel["month"].to_numpy()]
            + covid * panel["covid"].to_numpy()
            + delta[tag] * panel["post"].to_numpy()
            + kappa[tag] * panel["post_slope"].to_numpy()
        )
        if likelihood == "negbin":
            mu_alpha = pm.Normal("mu_log_alpha", 3, 1.5)
            sigma_alpha = pm.HalfNormal("sigma_log_alpha", 1.0)
            alpha = pm.math.exp(pm.Normal("log_alpha", mu_alpha, sigma_alpha, dims="tag"))
            pm.NegativeBinomial("y", mu=pm.math.exp(eta), alpha=alpha[tag], observed=y)
        else:  # "original": log(count + 1), normal
            sigma_t = pm.math.exp(
                pm.Normal("mu_log_sigma", -1.5, 1)
                + pm.HalfNormal("sigma_log_sigma", 0.5) * pm.Normal("sigma_z", 0, 1, dims="tag")
            )
            pm.Normal("y", mu=eta, sigma=sigma_t[tag], observed=np.log1p(y))
    return model


def sample(model, rep: progress.Reporter | None = None):
    import nutpie

    compiled = nutpie.compile_pymc_model(model)

    def callback(chains):  # live draws for `make progress`
        if rep is not None:
            rep.update(sum(c.finished_draws for c in chains), sum(c.divergences for c in chains))

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return nutpie.sample(
            compiled,
            draws=DRAWS,
            tune=TUNE,
            chains=CHAINS,
            seed=SEED,
            progress_bar=False,
            progress_callback=callback,
            progress_rate=2000,
        )


def log1p_offset_fix(panel: pd.DataFrame, n_tags: int) -> np.ndarray:
    pre = panel[(panel["post"] == 0) & (panel["covid"] == 0)]
    return (
        pre.groupby("tag_idx")["questions"]
        .apply(lambda s: np.log1p(s).mean())
        .reindex(range(n_tags))
        .to_numpy()
    )


# --- unpooled comparison ---------------------------------------------------------------


def unpooled(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (idx, tag), g in panel.groupby(["tag_idx", "tag"]):
        X = pd.get_dummies(g["month"], prefix="m", drop_first=True, dtype=float)
        X[["years", "covid", "post", "post_slope"]] = g[
            ["years", "covid", "post", "post_slope"]
        ].to_numpy()
        X = sm.add_constant(X.loc[:, X.std() > 0])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fit = sm.GLM(g["questions"].to_numpy(), X, family=sm.families.Poisson()).fit(
                scale="X2"
            )  # quasi-Poisson standard errors
        rows.append(
            {"tag_idx": idx, "tag": tag, "raw_delta": fit.params["post"], "raw_se": fit.bse["post"]}
        )
    return pd.DataFrame(rows)


# --- summaries ---------------------------------------------------------------------------


def save_draws(trace, features, path) -> None:
    """Posterior draws of each tag's delta (tags x draws) plus the hyperparameters, for P20."""
    d = pd.DataFrame(posterior(trace, "delta").T, columns=features["tag"])
    g = posterior(trace, "gamma")
    for i, name in enumerate(PREDICTORS):
        d[f"__gamma_{name}"] = g[i]
    d["__g0"] = posterior(trace, "g0")
    d.to_parquet(path, index=False)


def posterior(trace, name: str) -> np.ndarray:
    v = trace.posterior[name]
    return v.stack(sample=("chain", "draw")).transpose(..., "sample").to_numpy()


def diagnostics(trace) -> dict:
    import arviz as az

    names = [
        "g0",
        "gamma",
        "sigma_delta",
        "sigma_family",
        "family_effect",
        "beta0",
        "sigma_b",
        "a",
        "b",
        "delta",
        "kappa",
        "season",
        "covid",
    ]
    ess = {v: float(az.ess(trace, var_names=[v])[v].min()) for v in names}
    rhat = {v: float(az.rhat(trace, var_names=[v])[v].max()) for v in names}
    div = int(trace.sample_stats["diverging"].sum())
    return {
        "max_rhat": max(rhat.values()),
        "min_ess_bulk": min(ess.values()),
        "worst_ess": min(ess, key=ess.get),
        "divergences": div,
        "ess_by_param": {k: round(v) for k, v in ess.items()},
        "rhat_by_param": {k: round(v, 4) for k, v in rhat.items()},
    }


def pct(x):
    return 100 * (np.exp(x) - 1)


def summarise(trace, features, raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    d = posterior(trace, "delta")
    tags = features[
        ["tag", "family", "age_years_at_break", "size_2019_2021", "dup_share_2019_2021"]
    ].copy()
    tags["delta_mean"] = d.mean(axis=1)
    tags["pct"] = pct(np.median(d, axis=1))
    tags["pct_low"] = pct(np.percentile(d, 2.5, axis=1))
    tags["pct_high"] = pct(np.percentile(d, 97.5, axis=1))
    tags = tags.merge(raw[["tag", "raw_delta", "raw_se"]], on="tag", how="left")
    tags["raw_pct"] = pct(tags["raw_delta"])
    tags["shrink"] = tags["raw_delta"] - tags["delta_mean"]
    g = posterior(trace, "gamma")
    fam = posterior(trace, "family_effect")
    families = list(trace.posterior["family"].to_numpy())
    eff = {
        "g0_pct": float(pct(np.median(posterior(trace, "g0")))),
        "gamma_per_sd": {
            p: {
                "median": float(np.median(g[i])),
                "ci95": [float(np.percentile(g[i], 2.5)), float(np.percentile(g[i], 97.5))],
                "p_negative": float((g[i] < 0).mean()),
            }
            for i, p in enumerate(PREDICTORS)
        },
        "family_effect": {
            f: {
                "median": float(np.median(fam[i])),
                "ci95": [float(np.percentile(fam[i], 2.5)), float(np.percentile(fam[i], 97.5))],
            }
            for i, f in enumerate(families)
        },
        "sigma_delta": float(np.median(posterior(trace, "sigma_delta"))),
        "sigma_family": float(np.median(posterior(trace, "sigma_family"))),
        "predictor_sd": {
            "log_age": float(features["log_age"].std()),
            "log_size": float(features["log_size"].std()),
            "dup_share": float(features["dup_share_2019_2021"].std()),
        },
    }
    return tags.sort_values("pct").reset_index(drop=True), eff


# --- figures -----------------------------------------------------------------------------


def fig_top_bottom(tags: pd.DataFrame, path, n: int = 15) -> None:
    d = pd.concat([tags.head(n), tags.tail(n)]).reset_index(drop=True).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 9))
    y = np.arange(len(d))
    med = tags["pct"].median()
    for i, r in zip(y, d.itertuples(), strict=True):
        c = "#D55E00" if r.pct <= med else "#0072B2"
        ax.plot([r.pct_low, r.pct_high], [i, i], color=c, lw=1.5)
        ax.plot(r.pct, i, "o", color=c, ms=5)
    ax.axhline(n - 0.5, color="#cccccc", lw=0.8)
    ax.axvline(med, color="#999999", lw=0.8, ls=":")
    ax.set_yticks(y, [f"{t} ({f})" for t, f in zip(d["tag"], d["family"], strict=True)], fontsize=8)
    ax.set_xlabel("Change in questions vs the tag's own pre-2022 trend (%, 95% interval)")
    ax.set_title(
        f"Top 300 tags: the {n} that fell most and least (dotted: median tag)",
        loc="left",
        fontsize=11,
    )
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_shrinkage(tags: pd.DataFrame, path) -> None:
    fig, ax = plt.subplots(figsize=(6.5, 6))
    sizes = 10 + 60 * (np.log(tags["size_2019_2021"]) - 8) / 5
    ax.scatter(tags["raw_pct"], tags["pct"], s=sizes, color="#0072B2", alpha=0.5, lw=0)
    lim = [
        min(tags["raw_pct"].min(), tags["pct"].min()) - 2,
        max(tags["raw_pct"].max(), tags["pct"].max(), 0) + 5,
    ]
    ax.plot(lim, lim, color="#999999", lw=0.8)
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_xlabel("Unpooled estimate (each tag alone), %")
    ax.set_ylabel("Hierarchical estimate (partial pooling), %")
    ax.set_title(
        "Shrinkage: points pulled toward the average (dot size = tag size)", loc="left", fontsize=10
    )
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# --- run ---------------------------------------------------------------------------------

TASKS = {"data": 1, "unpooled": 2, "sample_negbin": 20, "sample_original": 15, "summaries": 1}


def _step(name, fn, total: int = 1):
    rep = progress.Reporter(JOB, name, total)
    try:
        out = fn(rep) if total > 1 else fn()
    except BaseException:
        rep.finish(0, status="failed")
        raise
    rep.finish(1)
    return out


def run() -> dict:
    progress.write_manifest(JOB, TASKS)
    t0 = time.monotonic()
    features, panel = _step("data", lambda: (lambda f: (f, load_panel(f)))(load_features()))
    raw = _step("unpooled", lambda: unpooled(panel))
    times = {}
    t = time.monotonic()
    n_draws = CHAINS * (DRAWS + TUNE)
    trace = _step(
        "sample_negbin", lambda rep: sample(build_model(panel, features, "negbin"), rep), n_draws
    )
    times["negbin_s"] = time.monotonic() - t
    t = time.monotonic()
    trace_log = _step(
        "sample_original", lambda rep: sample(build_model(panel, features, "log1p"), rep), n_draws
    )
    times["original_s"] = time.monotonic() - t

    def summaries():
        tags, eff = summarise(trace, features, raw)
        tags_log, eff_log = summarise(trace_log, features, raw)
        tags.round(4).to_csv(TABLES / "tag_effects.csv", index=False)
        tags_log.round(4).to_csv(TABLES / "tag_effects_original_log1p.csv", index=False)
        fig_top_bottom(tags, config.FIGURE_DIR / "tags_top_bottom.png")
        fig_shrinkage(tags, config.FIGURE_DIR / "tags_shrinkage.png")
        merged = tags.merge(tags_log[["tag", "pct"]], on="tag", suffixes=("", "_original"))
        fam = tags.groupby("family")["pct"].agg(["median", "size"]).sort_values("median")
        summary = {
            "n_tags": len(tags),
            "n_rows": len(panel),
            "sampling_seconds": times,
            "diagnostics": diagnostics(trace),
            "diagnostics_original": diagnostics(trace_log),
            "median_tag_pct": float(tags["pct"].median()),
            "tag_pct_range": [float(tags["pct"].min()), float(tags["pct"].max())],
            "share_tags_ci_below_zero": float((tags["pct_high"] < 0).mean()),
            "effects": eff,
            "effects_original": eff_log,
            "rank_corr_negbin_vs_original": float(
                merged[["pct", "pct_original"]].corr(method="spearman").iloc[0, 1]
            ),
            "shrinkage": {
                "sd_raw_pct_points": float(tags["raw_pct"].std()),
                "sd_pooled_pct_points": float(tags["pct"].std()),
                "corr_raw_pooled": float(tags[["raw_delta", "delta_mean"]].corr().iloc[0, 1]),
                "median_abs_shift_log": float(tags["shrink"].abs().median()),
            },
            "family_median_pct": fam.round(1).to_dict(orient="index"),
            "bottom_15": tags.head(15)[["tag", "family", "pct", "pct_low", "pct_high"]]
            .round(1)
            .to_dict(orient="records"),
            "top_15": tags.tail(15)[["tag", "family", "pct", "pct_low", "pct_high"]]
            .round(1)
            .to_dict(orient="records"),
            "total_seconds": time.monotonic() - t0,
        }
        (QA / "tags_summary.json").write_text(json.dumps(summary, indent=2))
        config.MODEL_DIR.mkdir(parents=True, exist_ok=True)
        save_draws(trace, features, config.MODEL_DIR / "tags_negbin_draws.parquet")
        return summary

    return _step("summaries", summaries)


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
