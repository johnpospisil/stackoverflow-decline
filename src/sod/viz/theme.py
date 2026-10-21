"""P26: shared chart theme (light and dark), validated for colour-vision deficiency.

Colours are assigned by role and never cycled. The four site groups use Okabe-Ito hues; the
counterfactual is not a group, so it is drawn in neutral ink (dashed line + grey band).
Validated with the dataviz skill's validate_palette.js (all pairs):
  light  #D55E00 #CC79A7 #0072B2 #009E73   pass (CVD 7.6 purple/green: needs a second cue)
  dark   #D55E00 #C673A1 #157BBB #009E73   pass (CVD 6.1 purple/green: needs a second cue)
Second cue: "SO in other languages" is always dashed and directly labelled. Text uses ink
tokens, never series colours.

Usage:
    from sod.viz import theme
    with theme.use("light"):
        fig, ax = plt.subplots(); ...; theme.save(fig, "hero_a")
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass

import matplotlib
import matplotlib.pyplot as plt

from sod import config

FONTS = ["Source Sans Pro", "Source Sans 3", "Helvetica Neue", "Arial", "DejaVu Sans"]


@dataclass(frozen=True)
class Palette:
    surface: str
    ink: str
    ink_muted: str
    grid: str
    band: str
    so: str
    so_language: str
    tech: str
    donor: str
    counterfactual: str


LIGHT = Palette(
    surface="#FCFCFB",
    ink="#1F2328",
    ink_muted="#5B636E",
    grid="#E6E6E3",
    band="#C9CED6",
    so="#D55E00",
    so_language="#CC79A7",
    tech="#0072B2",
    donor="#009E73",
    counterfactual="#4A525C",
)
DARK = Palette(
    surface="#1A1A19",
    ink="#ECEDEE",
    ink_muted="#A3A9B1",
    grid="#34363A",
    band="#4B5058",
    so="#D55E00",
    so_language="#C673A1",
    tech="#157BBB",
    donor="#009E73",
    counterfactual="#B9C0C9",
)
PALETTES = {"light": LIGHT, "dark": DARK}

GROUP_ROLE = {
    "treated": "so",
    "so_language": "so_language",
    "tech_exposed": "tech",
    "donor": "donor",
}
GROUP_LABEL = {
    "treated": "Stack Overflow",
    "so_language": "Stack Overflow in other languages",
    "tech_exposed": "Other tech Q&A sites",
    "donor": "Non-programming sites",
}
GROUP_STYLE = {
    "treated": {"lw": 2.6, "ls": "-"},
    "so_language": {"lw": 1.8, "ls": (0, (5, 2))},
    "tech_exposed": {"lw": 1.8, "ls": "-"},
    "donor": {"lw": 1.8, "ls": "-"},
}

_current = LIGHT


def palette() -> Palette:
    return _current


def group_color(group: str) -> str:
    return getattr(_current, GROUP_ROLE[group])


def rc(p: Palette) -> dict:
    return {
        "font.family": "sans-serif",
        "font.sans-serif": FONTS,
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.titleweight": "semibold",
        "axes.titlelocation": "left",
        "axes.labelsize": 10,
        "axes.labelcolor": p.ink_muted,
        "axes.edgecolor": p.ink_muted,
        "axes.facecolor": p.surface,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "axes.axisbelow": True,
        "grid.color": p.grid,
        "grid.linewidth": 0.8,
        "xtick.color": p.ink_muted,
        "ytick.color": p.ink_muted,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "text.color": p.ink,
        "figure.facecolor": p.surface,
        "savefig.facecolor": p.surface,
        "legend.frameon": False,
        "legend.fontsize": 9,
        "lines.linewidth": 2.0,
        "lines.solid_capstyle": "round",
        "svg.fonttype": "none",  # keep text as text in SVG
    }


@contextlib.contextmanager
def use(mode: str = "light"):
    global _current
    prev = _current
    _current = PALETTES[mode]
    with matplotlib.rc_context(rc(_current)):
        try:
            yield _current
        finally:
            _current = prev


# --- annotation helpers ------------------------------------------------------------------


def label_end(ax, x, y, text: str, color: str, dx: float = 6, **kw) -> None:
    """Direct label at a line's end: a colour swatch plus text in ink (never series colour)."""
    p = _current
    ax.annotate(
        "—",
        (x, y),
        xytext=(dx, 0),
        textcoords="offset points",
        va="center",
        ha="left",
        color=color,
        fontsize=12,
        fontweight="bold",
        annotation_clip=False,
    )
    ax.annotate(
        text,
        (x, y),
        xytext=(dx + 14, 0),
        textcoords="offset points",
        va="center",
        ha="left",
        color=p.ink,
        fontsize=kw.pop("fontsize", 9.5),
        annotation_clip=False,
        **kw,
    )


def event(ax, date, text: str, y: float = 0.98, span_end=None, align: str = "left") -> None:
    """A dotted vertical rule (or a shaded span) with a small muted label near the top."""
    p = _current
    if span_end is not None:
        ax.axvspan(date, span_end, color=p.band, alpha=0.35, lw=0, zorder=0)
    else:
        ax.axvline(date, color=p.ink_muted, lw=0.9, ls=(0, (1, 2)), zorder=1)
    ax.text(
        date,
        y,
        (" " + text) if align == "left" else (text + " "),
        transform=ax.get_xaxis_transform(),
        va="top",
        ha=align,
        fontsize=8.5,
        color=p.ink_muted,
    )


def title(fig, text: str, subtitle: str | None = None, x: float = 0.012) -> None:
    p = _current
    fig.text(x, 0.975, text, ha="left", va="top", fontsize=15, fontweight="semibold", color=p.ink)
    if subtitle:
        fig.text(x, 0.915, subtitle, ha="left", va="top", fontsize=10.5, color=p.ink_muted)


def source(fig, text: str, x: float = 0.012) -> None:
    fig.text(x, 0.015, text, ha="left", va="bottom", fontsize=8, color=_current.ink_muted)


def thousands(ax, axis: str = "y") -> None:
    fmt = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}")
    target = ax.yaxis if axis == "y" else ax.xaxis
    target.set_major_formatter(fmt)
    target.set_minor_formatter(matplotlib.ticker.NullFormatter())


def save(fig, name: str, mode: str | None = None) -> list:
    """Write PNG (200 dpi) and SVG to report/figures; dark versions get a _dark suffix."""
    mode = mode or ("dark" if _current is DARK else "light")
    stem = name if mode == "light" else f"{name}_dark"
    config.FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    paths = [config.FIGURE_DIR / f"{stem}.png", config.FIGURE_DIR / f"{stem}.svg"]
    fig.savefig(paths[0], dpi=200)
    fig.savefig(paths[1])
    plt.close(fig)
    return paths
