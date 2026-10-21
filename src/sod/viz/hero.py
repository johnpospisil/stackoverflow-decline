"""P26: hero chart, three alternatives, each in light and dark.

  A  hero_history  weekly questions 2008-2026 (log) vs the synthetic-control counterfactual
  B  hero_gap      2019-2026 on a linear scale, the gap shaded as "questions not asked"
  C  hero_groups   index 2019 = 100 (log): Stack Overflow vs synthetic vs the site groups

The counterfactual is the primary pre-registered estimate (monthly synthetic control, P17),
shown as a weekly rate (monthly count x 7 / days in month) so it sits on the weekly series.
Band: per-month 95% conformal interval.

Usage: python -m sod.viz.hero
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from sod import config  # noqa: E402
from sod.models import synth as sc  # noqa: E402
from sod.viz import theme  # noqa: E402

SOURCE = (
    "Data: Stack Exchange data dump 2026-Q3 (CC BY-SA 4.0). Synthetic control: 15 "
    "non-programming Stack Exchange sites, fitted on 2017-01 to 2022-11."
)
EVENTS = [
    (pd.Timestamp("2022-11-30"), "ChatGPT", None),
    (pd.Timestamp("2023-06-05"), "Moderator\nstrike", pd.Timestamp("2023-08-02")),
    (pd.Timestamp("2024-06-04"), "Staging Ground", None),
    (pd.Timestamp("2025-10-01"), "Opinion questions", None),
]


def data() -> dict:
    L = sc.load_logs().loc[: sc.END]
    pre, post = sc.masks(L.index)
    D = sc.demean(L, pre)
    main = sc.synth(D, sc.TREATED, sc.DONORS, pre, post)
    _, ci = sc.pysyncon_fit_and_ci(D, pre, post)
    ci = ci.set_index("period")
    so_log = L[sc.TREATED]
    cf_log = so_log - main["gap"]
    days = pd.Series(L.index.days_in_month, index=L.index)
    per_week = 7 / days
    m = pd.DataFrame({"actual": np.exp(so_log), "cf": np.exp(cf_log)})
    m["cf_low"] = np.exp(so_log - ci["upper_ci"]).reindex(m.index)
    m["cf_high"] = np.exp(so_log - ci["lower_ci"]).reindex(m.index)
    weekly_rate = m.mul(per_week, axis=0)
    post_idx = L.index[L.index > sc.PRE_END]
    missing = float((m.loc[post_idx, "cf"] - m.loc[post_idx, "actual"]).sum())
    w = pd.read_parquet(config.PANEL_DIR / "site_week.parquet")
    w = w[(w["site"] == sc.TREATED) & ~w["partial_period"]].set_index("period")["questions"]
    # group medians, index 2019 = 100
    month = pd.read_parquet(config.PANEL_DIR / "site_month.parquet")
    month = month[~month["partial_period"] & (month["period"] >= "2015-01-01")]
    month["group"] = month["site"].map(config.site_group)
    base = month[month["period"].dt.year == 2019].groupby("site")["questions"].mean()
    month["index"] = 100 * month["questions"] / month["site"].map(base)
    groups = month.groupby(["group", "period"])["index"].median().unstack(0)
    syn_index = 100 * m["cf"] / m.loc[m.index.year == 2019, "actual"].mean()
    return {
        "monthly": m,
        "weekly_rate": weekly_rate,
        "weekly": w,
        "att": main["att_log"],
        "missing": missing,
        "groups": groups,
        "syn_index": syn_index,
        "ci_avg": (float(sc.pct(ci["lower_ci"].mean())), float(sc.pct(ci["upper_ci"].mean()))),
    }


def _events(ax, top: float = 0.97):
    for i, (d, label, end) in enumerate(EVENTS):
        theme.event(ax, d, label, y=top - 0.055 * (i % 2), span_end=end)


def hero_history(d: dict, mode: str) -> list:
    with theme.use(mode) as p:
        fig, ax = plt.subplots(figsize=(12, 6.2))
        fig.subplots_adjust(left=0.07, right=0.80, top=0.84, bottom=0.11)
        w = d["weekly"]
        r = d["weekly_rate"]
        post = r.index > sc.PRE_END
        ax.fill_between(
            r.index[post],
            r["cf_low"][post],
            r["cf_high"][post],
            color=p.band,
            alpha=0.6,
            lw=0,
            step="mid",
        )
        ax.plot(r.index, r["cf"], color=p.counterfactual, lw=1.6, ls=(0, (4, 2)))
        ax.plot(w.index, w.to_numpy(), color=p.so, lw=1.1)
        ax.set_yscale("log")
        ax.set_ylim(150, 80000)
        ax.set_xlim(pd.Timestamp("2008-09-15"), pd.Timestamp("2026-12-31"))  # public launch
        theme.thousands(ax)
        ax.set_ylabel("Questions per week (log scale)")
        _events(ax)
        theme.label_end(
            ax,
            r.index[-1],
            r["cf"].iloc[-1],
            "Expected without ChatGPT\n(synthetic control, 95% band)",
            p.counterfactual,
        )
        theme.label_end(ax, w.index[-1], w.iloc[-3:].mean(), "Stack Overflow", p.so)
        pct = sc.pct(d["att"])
        theme.title(
            fig,
            f"Stack Overflow questions are {abs(pct):.0f}% below what comparable sites predict",
            "New questions per week, 2008–2026. The dashed line is a 'synthetic' Stack "
            "Overflow built from sites ChatGPT barely touched.",
        )
        theme.source(fig, SOURCE)
        return theme.save(fig, "hero_history", mode)


def hero_gap(d: dict, mode: str) -> list:
    with theme.use(mode) as p:
        fig, ax = plt.subplots(figsize=(12, 6.2))
        fig.subplots_adjust(left=0.07, right=0.80, top=0.84, bottom=0.11)
        r = d["weekly_rate"].loc["2019-01-01":]
        w = d["weekly"].loc["2019-01-01":]
        post = r.index > sc.PRE_END
        ax.fill_between(
            r.index[post],
            r["cf_low"][post],
            r["cf_high"][post],
            color=p.band,
            alpha=0.6,
            lw=0,
            step="mid",
        )
        ax.fill_between(
            r.index[post], r["actual"][post], r["cf"][post], color=p.so, alpha=0.12, lw=0
        )
        ax.plot(r.index, r["cf"], color=p.counterfactual, lw=1.6, ls=(0, (4, 2)))
        ax.plot(w.index, w.to_numpy(), color=p.so, lw=1.1)
        ax.set_ylim(0, 48000)
        ax.set_xlim(pd.Timestamp("2019-01-01"), pd.Timestamp("2026-12-31"))
        theme.thousands(ax)
        ax.set_ylabel("Questions per week")
        _events(ax)
        theme.label_end(
            ax, r.index[-1], r["cf"].iloc[-1], "Expected without ChatGPT", p.counterfactual
        )
        theme.label_end(ax, w.index[-1], w.iloc[-1], "Stack Overflow", p.so)
        target = pd.Timestamp("2024-09-01")
        ax.annotate(
            f"≈ {d['missing'] / 1e6:.1f} million questions not asked\nDec 2022 – Sep 2026 (shaded)",
            xy=(target, 0.5 * (r.loc[target, "cf"] + r.loc[target, "actual"])),
            xytext=(pd.Timestamp("2023-03-01"), 4200),
            ha="center",
            va="center",
            fontsize=11,
            color=p.ink,
            arrowprops={"arrowstyle": "-", "color": p.ink_muted, "lw": 0.8},
            bbox={"fc": p.surface, "ec": "none", "pad": 3},
            zorder=5,
        )
        theme.title(
            fig,
            "Since ChatGPT, millions of questions were never asked",
            "New Stack Overflow questions per week vs the synthetic-control estimate "
            "of what would have happened without ChatGPT.",
        )
        theme.source(fig, SOURCE)
        return theme.save(fig, "hero_gap", mode)


def hero_groups(d: dict, mode: str) -> list:
    with theme.use(mode) as p:
        fig, ax = plt.subplots(figsize=(12, 6.2))
        fig.subplots_adjust(left=0.07, right=0.76, top=0.84, bottom=0.11)
        g = d["groups"]
        order = ["donor", "tech_exposed", "so_language", "treated"]
        syn = d["syn_index"].loc["2017-01-01":]
        ax.plot(syn.index, syn, color=p.counterfactual, lw=1.6, ls=(0, (4, 2)))
        ends = {}
        for grp in order:
            s = g[grp].dropna()
            ax.plot(s.index, s, color=theme.group_color(grp), **theme.GROUP_STYLE[grp])
            ends[grp] = s
        ax.set_yscale("log")
        ax.set_ylim(0.4, 250)
        ax.set_yticks([1, 3, 10, 30, 100], ["1", "3", "10", "30", "100"])
        ax.set_xlim(pd.Timestamp("2015-01-01"), pd.Timestamp("2026-12-31"))
        ax.set_ylabel("Questions per month, index (2019 = 100, log scale)")
        _events(ax)
        labels = {
            "donor": "Non-programming sites (median)",
            "tech_exposed": "Other tech Q&A sites (median)",
            "so_language": "Stack Overflow in other\nlanguages (median)",
            "treated": "Stack Overflow",
        }
        ys = {k: float(v.iloc[-3:].median()) for k, v in ends.items()}
        ys["syn"] = float(syn.iloc[-1])
        # nudge end labels apart on the log scale
        placed = []
        for k in sorted(ys, key=ys.get, reverse=True):
            y = ys[k]
            for py in placed:
                if abs(np.log10(y) - np.log10(py)) < 0.09:
                    y = py / 10**0.09
            placed.append(y)
            if k == "syn":
                theme.label_end(ax, syn.index[-1], y, "Synthetic Stack Overflow", p.counterfactual)
            else:
                theme.label_end(ax, ends[k].index[-1], y, labels[k], theme.group_color(k))
        theme.title(
            fig,
            "Programming Q&A fell far faster than the rest of Stack Exchange",
            "Questions per month, each site indexed to its 2019 average. Groups show "
            "the median site.",
        )
        theme.source(fig, SOURCE)
        return theme.save(fig, "hero_groups", mode)


def run() -> list:
    d = data()
    out = []
    for mode in ("light", "dark"):
        out += hero_history(d, mode) + hero_gap(d, mode) + hero_groups(d, mode)
    return out


if __name__ == "__main__":
    for path in run():
        print(path)
