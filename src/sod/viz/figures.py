"""P27: charts 2-7 from the plan (04-stackoverflow-decline.md section 6), light and dark.

  fig2_tags        top 50 tags by 2019-21 size: change vs own pre-trend, 95% intervals, by family
  fig3_thin_data   tag age vs change (top 297) and post-2021 tags vs the top 300
  fig4_retention   newcomer cohort x months since first post heatmap
  fig5_mix         question mix 2021 vs 2025 (H3 measures), actual and tag mix held at 2021
  fig6_sites       small multiples: every site indexed to 2019 = 100, Stack Overflow ghosted
  fig7_responsive  % answered within 24 h / 7 days (weekly, 95% bands) and answer speed

Inputs are the saved outputs of P13-P24 (report/tables, report/qa, panels).

Usage: python -m sod.viz.figures
"""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from sod import config  # noqa: E402
from sod.models import responsiveness as resp  # noqa: E402
from sod.viz import theme  # noqa: E402

REPORT = config.REPORT_DIR
SOURCE = "Data: Stack Exchange data dump 2026-Q3 (CC BY-SA 4.0)."
CHATGPT = pd.Timestamp(config.BREAK_DATE)
OPINION = pd.Timestamp("2025-10-01")


def _family_legend(ax, loc="lower right"):
    handles = [
        plt.Line2D([], [], ls="", ms=7, label=g, **theme.family_style(g))
        for g in theme.FAMILY_ORDER
    ]
    ax.legend(handles=handles, loc=loc, fontsize=8.5, handletextpad=0.3)


# --- 2 -----------------------------------------------------------------------------------


def fig2_tags(mode: str) -> list:
    t = pd.read_csv(REPORT / "tables" / "tag_effects.csv")
    top = t.nlargest(50, "size_2019_2021").sort_values("pct", ascending=False)
    with theme.use(mode) as p:
        fig, ax = plt.subplots(figsize=(9, 12))
        fig.subplots_adjust(left=0.2, right=0.97, top=0.92, bottom=0.07)
        y = np.arange(len(top))
        for i, r in zip(y, top.itertuples(), strict=True):
            st = theme.family_style(theme.family_group(r.family))
            ax.plot(
                [r.pct_low, r.pct_high], [i, i], color=st["color"], lw=1.4, solid_capstyle="butt"
            )
            ax.plot(r.pct, i, ms=6, ls="", **st)
        ax.set_yticks(y, top["tag"], fontsize=9)
        ax.set_ylim(-1, len(top))
        ax.grid(axis="x", color=p.grid)
        ax.grid(axis="y", visible=False)
        med = t["pct"].median()
        ax.axvline(med, color=p.ink_muted, lw=0.9, ls=(0, (1, 2)))
        ax.text(
            med,
            -0.9,
            f" median of 297 tags: {med:.0f}%",
            fontsize=8.5,
            color=p.ink_muted,
            va="bottom",
        )
        ax.set_xlabel(
            "Change in questions vs the tag's own pre-2022 trend, Dec 2022 – Sep 2026 "
            "(%, 95% interval)"
        )
        _family_legend(ax, loc="upper right")
        theme.title(
            fig,
            "Every major tag fell; data tags fell most, mobile least",
            "The 50 largest Stack Overflow tags (2019–21), each against its own pre-2022 trend. "
            "Fast-growing tags' trends rise steeply, which enlarges their gaps.",
            x=0.02,
        )
        theme.source(fig, SOURCE + " Tags at the time of asking.", x=0.02)
        return theme.save(fig, "fig2_tags", mode)


# --- 3 -----------------------------------------------------------------------------------


def fig3_thin_data(mode: str) -> list:
    t = pd.read_csv(REPORT / "tables" / "tag_effects.csv")
    new = pd.read_csv(REPORT / "tables" / "new_tags_lifecycle.csv").dropna(subset=["gap_pct"])
    s = json.loads((REPORT / "qa" / "thin_data_summary.json").read_text())
    with theme.use(mode) as p:
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 6), gridspec_kw={"width_ratios": [2.2, 1]})
        fig.subplots_adjust(left=0.07, right=0.97, top=0.8, bottom=0.15, wspace=0.25)
        for g in theme.FAMILY_ORDER:
            d = t[t["family"].map(theme.family_group) == g]
            a1.plot(
                d["age_years_at_break"], d["pct"], ls="", ms=5, alpha=0.85, **theme.family_style(g)
            )
        lx = np.log(t["age_years_at_break"])
        b = np.polyfit(lx, t["pct"], 1)
        xs = np.linspace(lx.min(), lx.max(), 50)
        a1.plot(np.exp(xs), np.polyval(b, xs), color=p.ink, lw=1.6)
        resid = t["pct"] - np.polyval(b, lx)
        for i in resid.nlargest(4).index:
            a1.annotate(
                t.loc[i, "tag"],
                (t.loc[i, "age_years_at_break"], t.loc[i, "pct"]),
                xytext=(-4, 4),
                textcoords="offset points",
                ha="right",
                fontsize=8,
                color=p.ink_muted,
            )
        a1.set_xscale("log")
        a1.set_xticks([5, 7, 10, 14], ["5", "7", "10", "14"])
        a1.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        a1.set_xlabel("Tag age at ChatGPT (years, log scale; 14 = there since launch)")
        a1.set_ylabel("Change vs own pre-2022 trend (%)")
        a1.set_title("Older tags fell less, not more", fontsize=11)
        _family_legend(a1, loc="upper left")
        # right: new tags vs top 300
        top_med = s["b_new_tags"]["top300_median_pct"]
        rng = np.random.default_rng(1)
        a2.scatter(
            rng.normal(0, 0.06, len(new)),
            new["gap_pct"].clip(upper=150),
            s=16,
            color=p.tech,
            alpha=0.8,
            lw=0,
        )
        a2.scatter(
            1 + rng.normal(0, 0.06, len(t)), t["pct"], s=10, color=p.ink_muted, alpha=0.5, lw=0
        )
        for x, v in ((0, new["gap_pct"].median()), (1, top_med)):
            a2.plot([x - 0.25, x + 0.25], [v, v], color=p.ink, lw=2)
            a2.text(x + 0.28, v, f"{v:.0f}%", va="center", fontsize=9, color=p.ink)
        a2.set_xticks([0, 1], ["Tags new after\n2021-09 (66)", "Top 300 tags\n(297)"])
        a2.set_xlim(-0.5, 1.6)
        a2.set_ylabel("Change vs counterfactual (%)")
        a2.set_title("Post-training-cut-off tags held up better", fontsize=11)
        theme.title(
            fig,
            "The 'thin training data' test: half supported",
            "H2 predicted older tags would fall more (they fell less) and tags created "
            "after the first ChatGPT training cut-off would fall less (they did).",
        )
        theme.source(
            fig,
            SOURCE + " Right: new tags vs pre-ChatGPT tags of similar early size; "
            "top 300 vs own trend (different yardsticks). .NET 8 (+274%) drawn at 150.",
        )
        return theme.save(fig, "fig3_thin_data", mode)


# --- 4 -----------------------------------------------------------------------------------


def fig4_retention(mode: str, max_k: int = 24) -> list:
    ca = pd.read_parquet(config.PARQUET_DIR / "cohort_activity" / f"site={config.TREATED}")
    ca["cohort_month"] = pd.to_datetime(ca["cohort_month"])
    ca = ca[(ca["cohort_month"] >= "2016-01-01") & ca["months_since"].between(1, max_k)]
    ca["share"] = 100 * ca["active"] / ca["cohort_size"]
    grid = ca.pivot(index="cohort_month", columns="months_since", values="share")
    last = pd.Timestamp("2026-09-01")
    for c in grid.index:
        k_obs = (last.year - c.year) * 12 + last.month - c.month
        grid.loc[c, grid.columns > k_obs] = np.nan
    with theme.use(mode) as p:
        fig, ax = plt.subplots(figsize=(10, 8))
        fig.subplots_adjust(left=0.1, right=0.9, top=0.86, bottom=0.08)
        cmap = theme.sequential_cmap()
        cmap.set_bad(p.surface)
        im = ax.imshow(
            grid.to_numpy(), aspect="auto", cmap=cmap, vmin=0, vmax=12, interpolation="nearest"
        )
        ys = [i for i, d in enumerate(grid.index) if d.month == 1]
        ax.set_yticks(ys, [grid.index[i].year for i in ys])
        ax.set_xticks(range(0, max_k, 3), range(1, max_k + 1, 3))
        ax.grid(False)
        ax.set_xlabel("Months since first post")
        ax.set_ylabel("Month of first post")
        k = list(grid.index).index(pd.Timestamp("2022-12-01"))
        ax.axhline(k - 0.5, color=p.ink, lw=1, ls=(0, (2, 2)))
        ax.text(max_k - 0.6, k - 0.8, "ChatGPT", ha="right", va="bottom", fontsize=8.5, color=p.ink)
        cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02, extend="max")
        cb.set_label("% of the cohort posting in that month")
        cb.outline.set_visible(False)
        theme.title(
            fig,
            "Fewer newcomers come back",
            "Stack Overflow users by month of their first question or answer: share "
            "posting again N months later.",
        )
        theme.source(fig, SOURCE + " Blank: not yet observed.")
        return theme.save(fig, "fig4_retention", mode)


# --- 5 -----------------------------------------------------------------------------------


def fig5_mix(mode: str) -> list:
    s = json.loads((REPORT / "qa" / "question_mix_summary.json").read_text())
    m = {r["measure"]: r for r in s["measures"]}
    panels = [
        ("body_length", "Median question length\n(characters)", "{:,.0f}", 1),
        ("code_share", "Share with a code block", "{:.1f}%", 100),
        ("dup_share", "Closed as duplicate\nwithin 30 days", "{:.1f}%", 100),
        ("first_time_share", "From first-time\naskers", "{:.1f}%", 100),
    ]
    with theme.use(mode) as p:
        fig, axes = plt.subplots(1, 4, figsize=(13, 5))
        fig.subplots_adjust(left=0.05, right=0.97, top=0.74, bottom=0.12, wspace=0.55)
        for ax, (key, label, fmt, k) in zip(axes, panels, strict=True):
            r = m[key]
            v21, v25, v25r = k * r["y2021"], k * r["y2025"], k * r["y2025_tagmix2021"]
            ax.plot([0, 1], [v21, v25], "o-", color=p.ink_muted, lw=1.4, ms=5)
            ax.plot([0, 1], [v21, v25r], "o-", color=p.so, lw=2.4, ms=6)
            ax.annotate(
                fmt.format(v21),
                (0, v21),
                xytext=(-8, 0),
                textcoords="offset points",
                ha="right",
                va="center",
                fontsize=9,
                color=p.ink,
            )
            ax.annotate(
                fmt.format(v25r),
                (1, v25r),
                xytext=(8, 0),
                textcoords="offset points",
                ha="left",
                va="center",
                fontsize=9,
                color=p.ink,
            )
            close = abs(v25 - v25r) < 0.08 * (max(v21, v25, v25r) - min(v21, v25, v25r))
            ax.annotate(
                fmt.format(v25) + " actual",
                (1, v25),
                xytext=(8, -12 if close else 0),
                textcoords="offset points",
                ha="left",
                va="center",
                fontsize=7.5,
                color=p.ink_muted,
            )
            pred = "up" if r["predicted"] > 0 else "down"
            ok = "as predicted" if r["moves_as_predicted"] else "not as predicted"
            ax.set_title(f"{label}\nH3: {pred} · {ok}", fontsize=10)
            lo, hi = sorted([v21, v25, v25r])[0], sorted([v21, v25, v25r])[-1]
            pad = 0.35 * (hi - lo)
            ax.set_ylim(lo - pad, hi + pad)
            ax.set_xticks([0, 1], ["2021", "2025"])
            ax.set_xlim(-0.6, 1.9)
            ax.grid(False)
            ax.spines[["left"]].set_visible(False)
            ax.set_yticks([])
        theme.title(
            fig,
            "Questions got longer; little else changed the predicted way",
            "Stack Overflow questions, 2021 vs 2025. Orange: 2025 with the 2021 tag mix "
            "(within-topic change); grey: actual 2025.",
        )
        theme.source(
            fig,
            SOURCE + " Deleted questions are not in the dump; only the length "
            "change survives the deletion bound.",
        )
        return theme.save(fig, "fig5_mix", mode)


# --- 6 -----------------------------------------------------------------------------------


def fig6_sites(mode: str) -> list:
    month = pd.read_parquet(config.PANEL_DIR / "site_month.parquet")
    month = month[~month["partial_period"] & (month["period"] >= "2017-01-01")]
    base = month[month["period"].dt.year == 2019].groupby("site")["questions"].mean()
    month["index"] = 100 * month["questions"] / month["site"].map(base)
    wide = month.pivot(index="period", columns="site", values="index").where(lambda d: d > 0)
    order = (
        [config.TREATED]
        + list(config.SITE_GROUPS["so_language"])
        + list(config.SITE_GROUPS["tech_exposed"])
        + list(config.SITE_GROUPS["donor"])
    )
    names = {s: s.replace(".stackexchange.com", "").replace(".com", "") for s in order}
    with theme.use(mode) as p:
        fig, axes = plt.subplots(5, 6, figsize=(15, 12), sharex=True, sharey=True)
        fig.subplots_adjust(left=0.05, right=0.98, top=0.88, bottom=0.05, hspace=0.45, wspace=0.12)
        so = wide[config.TREATED]
        for ax, site in zip(axes.flat, order, strict=False):
            grp = config.site_group(site)
            ax.plot(so.index, so, color=p.so, lw=1.0, alpha=0.35 if site != config.TREATED else 1)
            ax.plot(
                wide.index,
                wide[site],
                color=theme.group_color(grp),
                **{**theme.GROUP_STYLE[grp], "lw": 1.6},
            )
            ax.axvline(CHATGPT, color=p.ink_muted, lw=0.7, ls=(0, (1, 2)))
            last = wide[site].dropna().iloc[-3:].median()
            ax.set_title(f"{names[site]}  ·  {last:.0f}", fontsize=8.5, loc="left")
            ax.set_yscale("log")
            ax.set_ylim(0.3, 300)
            ax.set_yticks([1, 10, 100], ["1", "10", "100"])
            ax.tick_params(labelsize=7)
        for ax in list(axes.flat)[len(order) :]:
            ax.axis("off")
        legend_ax = list(axes.flat)[len(order)]
        handles = [
            plt.Line2D(
                [],
                [],
                color=theme.group_color(g),
                label=theme.GROUP_LABEL[g],
                **{**theme.GROUP_STYLE[g], "lw": 2},
            )
            for g in theme.GROUP_ROLE
        ]
        handles.append(
            plt.Line2D([], [], color=p.so, alpha=0.35, lw=1, label="Stack Overflow (for reference)")
        )
        legend_ax.legend(handles=handles, loc="center left", fontsize=8.5)
        theme.title(
            fig,
            "Every site fell, but programming Q&A fell furthest",
            "Questions per month, each site indexed to its 2019 average (log scale). "
            "Number: latest level. Faint orange in every panel: Stack Overflow.",
        )
        theme.source(fig, SOURCE)
        return theme.save(fig, "fig6_sites", mode)


# --- 7 -----------------------------------------------------------------------------------


def fig7_responsive(mode: str) -> list:
    w = pd.read_parquet(config.PANEL_DIR / "site_week.parquet")
    w = w[(w["site"] == config.TREATED) & (w["period"] >= "2017-01-01") & ~w["partial_period"]]
    speed = resp.conditional_speed()
    with theme.use(mode) as p:
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 5.6))
        fig.subplots_adjust(left=0.06, right=0.88, top=0.8, bottom=0.12, wspace=0.42)
        for k, n, label, ls in (
            ("answered_7d", "eligible_7d", "within 7 days", "-"),
            ("answered_24h", "eligible_24h", "within 24 hours", (0, (4, 2))),
        ):
            d = w[w[n] > 0]
            lo, hi = resp.wilson(d[k].to_numpy(), d[n].to_numpy())
            rate = 100 * d[k] / d[n]
            a1.fill_between(d["period"], 100 * lo, 100 * hi, color=p.so, alpha=0.18, lw=0)
            a1.plot(d["period"], rate, color=p.so, lw=1.3, ls=ls)
            theme.label_end(
                a1, d["period"].iloc[-1], rate.iloc[-12:].median(), f"answered {label}", p.so
            )
        a1.set_ylim(40, 82)
        a1.set_ylabel("% of new questions (weekly, 95% band)")
        a1.set_title("Share of questions answered", fontsize=11)
        a2.plot(speed["period"], speed["median_hours_if_answered_7d"], color=p.tech, lw=2)
        a2.plot(
            speed["period"], speed["p75_hours_if_answered_7d"], color=p.tech, lw=1.3, ls=(0, (4, 2))
        )
        theme.label_end(
            a2,
            speed["period"].iloc[-1],
            speed["median_hours_if_answered_7d"].iloc[-1],
            "median",
            p.tech,
        )
        theme.label_end(
            a2,
            speed["period"].iloc[-1],
            speed["p75_hours_if_answered_7d"].iloc[-1],
            "slowest quarter starts",
            p.tech,
        )
        a2.set_ylabel("Hours to first answer")
        a2.set_title("Wait for an answer (questions answered within 7 days)", fontsize=11)
        for ax in (a1, a2):
            theme.event(ax, CHATGPT, "ChatGPT", y=0.99)
            theme.event(ax, OPINION, "Opinion\nquestions", y=0.99)
        theme.title(
            fig,
            "Fewer questions get answered, and answers take longer",
            "Stack Overflow, 2017–2026. Fixed windows: a question counts only if its "
            "whole window ends before the 2026-09-30 cut-off.",
        )
        theme.source(
            fig, SOURCE + " From Oct 2025, opinion-based questions change what 'answered' means."
        )
        return theme.save(fig, "fig7_responsive", mode)


# --- 8 -----------------------------------------------------------------------------------


def fig8_robustness(mode: str) -> list:
    """Forest plot of the pre-registered robustness variants (P18) in the shared theme."""
    d = pd.read_csv(REPORT / "tables" / "robustness.csv", dtype={"id": str}).iloc[::-1]
    d = d.reset_index(drop=True)
    with theme.use(mode) as p:
        fig, ax = plt.subplots(figsize=(10, 0.36 * len(d) + 1.9))
        fig.subplots_adjust(left=0.33, right=0.93, top=1 - 1.0 / fig.get_figheight(), bottom=0.12)
        ax.axvspan(-10, 0, color=p.band, alpha=0.45, lw=0, zorder=0)
        ax.axvline(0, color=p.ink_muted, lw=0.8)
        primary = float(d.loc[d["id"] == "0", "att_pct"].iloc[0])
        ax.axvline(primary, color=p.so, lw=0.9, ls=(0, (1, 2)))
        for i, r in d.iterrows():
            sup = r["group"] == "Supporting"
            c = p.so if r["id"] == "0" else (p.counterfactual if sup else p.tech)
            if pd.notna(r["low"]):
                dotted = str(r.get("range_not_ci")) == "True"
                ax.plot([r["low"], r["high"]], [i, i], color=c, lw=1.6, ls=":" if dotted else "-")
            ax.plot(
                r["att_pct"], i, "s" if sup else "o", color=c, ms=6.5 if r["id"] == "0" else 5.5
            )
            ax.text(
                1.5,
                i,
                f"{r['att_pct']:.0f}%".replace("-", "\u2212"),
                va="center",
                fontsize=8.5,
                color=p.ink,
            )
        ax.set_yticks(range(len(d)), d["label"], fontsize=8.5)
        for lab, r in zip(ax.get_yticklabels(), d.itertuples(), strict=True):
            lab.set_color(p.ink if r.id == "0" else p.ink_muted)
        ax.set_xlim(-100, 9)
        ax.set_ylim(-1.3, len(d) - 0.5)
        ax.grid(axis="x", color=p.grid)
        ax.grid(axis="y", visible=False)
        ax.set_xlabel("Average gap vs counterfactual, Dec 2022 – Sep 2026 (%, 95% interval)")
        ax.text(
            -9.6,
            -1.1,
            "smaller than the\n\u221210% threshold",
            fontsize=7.5,
            color=p.ink_muted,
            va="bottom",
        )
        theme.title(
            fig,
            "Every variant of the estimate tells the same story",
            "Circles: synthetic-control variants (pre-registered); squares: other methods. "
            "Dotted bar: range across 15 refits.",
            x=0.02,
        )
        theme.source(fig, SOURCE, x=0.02)
        return theme.save(fig, "fig8_robustness", mode)


FIGURES = [
    fig2_tags,
    fig3_thin_data,
    fig4_retention,
    fig5_mix,
    fig6_sites,
    fig7_responsive,
    fig8_robustness,
]


def run() -> list:
    out = []
    for mode in ("light", "dark"):
        for f in FIGURES:
            out += f(mode)
    return out


if __name__ == "__main__":
    for path in run():
        print(path)
