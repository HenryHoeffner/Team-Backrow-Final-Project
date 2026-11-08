"""Shared look for every graphic: palette, fonts, header/footer and the bin legend.

Bins use a diverging palette: warm vermillion = most changed (Q1), neutral gray = middle
(Q3), deep blue = least changed (Q5). It avoids the red/green pairing (hard for red-green
colorblind readers), and every chart also prints the Q label so the bin never depends on
color alone. Adjacent-pair separation was checked in OKLab, including simulated protan,
deutan and tritan vision (worst pair Q2-Q3, delta E 7.3, which is why the labels are always shown).
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

BIN_COLORS = {1: "#b8352a", 2: "#e8875a", 3: "#9e9a91", 4: "#6aa3df", 5: "#1c5cab"}
BIN_TEXT = {1: "white", 2: "#1d1d1b", 3: "#1d1d1b", 4: "#1d1d1b", 5: "white"}  # text on a bin fill
BIN_WORDS = {1: "most changed", 3: "typical", 5: "least changed"}

SURFACE = "#fcfcfb"
INK = "#1d1d1b"
INK_2 = "#55534e"
MUTED = "#8a877f"
GRID = "#ebe9e4"
BASELINE = "#3d3b37"  # the S&P 500 line
DPI = 200

FONT_STACK = ["Avenir Next", "Helvetica Neue", "Helvetica", "DejaVu Sans"]


def apply_theme() -> None:
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": FONT_STACK,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK_2,
        "xtick.color": INK_2,
        "ytick.color": INK_2,
        "axes.axisbelow": True,
        "hatch.color": "white",
        "hatch.linewidth": 1.2,
    })


def bin_color(b: int) -> str:
    return BIN_COLORS[int(b)]


def style_axes(ax, ygrid: bool = True) -> None:
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="both", length=0, labelsize=8, pad=5)
    if ygrid:
        ax.grid(axis="y", color=GRID, lw=0.8)


def header(fig, title: str, subtitle: str, headline: str = "", detail: str = "",
           x: float = 0.06, top_in: float = 0.2) -> None:
    """Row 1: title (left) and a bold headline stat (right). Row 2: subtitle. Row 3: a
    muted detail line. Spacing is in inches so short and tall figures match."""
    h = fig.get_figheight()
    y = 1 - top_in / h
    fig.text(x, y, title, ha="left", va="top", fontsize=15, fontweight="bold", color=INK)
    if headline:
        fig.text(0.965, y - 0.03 / h, headline, ha="right", va="top", fontsize=9, color=INK, fontweight="bold")
    fig.text(x, y - 0.34 / h, subtitle, ha="left", va="top", fontsize=8.3, color=INK_2)
    if detail:
        fig.text(x, y - 0.55 / h, detail, ha="left", va="top", fontsize=7.8, color=MUTED)


def zero_is_sp500(fmt):
    """Tick formatter that writes the 0 line as 'S&P 500' and uses a true minus sign."""
    def f(v, _=None):
        if abs(v) < 1e-9:
            return "S&P 500"
        return fmt(v).replace("-", "\u2212")
    return f


def footnote(fig, text: str, x: float = 0.06, y_in: float = 0.11) -> None:
    fig.text(x, y_in / fig.get_figheight(), text, ha="left", va="bottom", fontsize=6.3, color=MUTED, linespacing=1.45)


def bin_scale(fig, x: float, y_in: float, partial: bool = False) -> None:
    """A small diverging key, 'Bins: most changed [Q1]..[Q5] least changed', with its
    bottom edge y_in inches above the figure bottom. Sizes are in inches."""
    w, h = fig.get_figwidth(), fig.get_figheight()
    cw, ch = 0.27 / w, 0.19 / h
    y = y_in / h
    fig.text(x, y + ch / 2, "Bins:  most changed", ha="left", va="center", fontsize=7, color=INK_2)
    x0 = x + 0.95 / w
    for b in range(1, 6):
        fig.patches.append(Rectangle((x0 + (b - 1) * cw, y), cw * 0.92, ch,
                                     transform=fig.transFigure, color=BIN_COLORS[b], lw=0))
        fig.text(x0 + (b - 1) * cw + cw * 0.46, y + ch / 2, f"Q{b}", ha="center", va="center",
                 fontsize=6.5, color=BIN_TEXT[b], fontweight="bold")
    end = x0 + 5 * cw + 0.06 / w
    fig.text(end, y + ch / 2, "least changed", ha="left", va="center", fontsize=7, color=INK_2)
    if partial:
        px = end + 0.95 / w
        fig.patches.append(Rectangle((px, y), cw * 0.92, ch, transform=fig.transFigure,
                                     facecolor=MUTED, edgecolor="none", hatch="////", alpha=0.75))
        fig.text(px + cw + 0.05 / w, y + ch / 2, "window still open (partial year)", ha="left",
                 va="center", fontsize=7, color=INK_2)


def chip(ax, x: float, y: float, b: int, transform, fontsize: float = 6.8) -> None:
    """A rounded bin badge ('Q2') centred at (x, y) in the given transform."""
    ax.annotate(f"Q{int(b)}", (x, y), xycoords=transform, ha="center", va="center", fontsize=fontsize,
                fontweight="bold", color=BIN_TEXT[int(b)], annotation_clip=False,
                bbox=dict(boxstyle="round,pad=0.28,rounding_size=0.5", fc=BIN_COLORS[int(b)], ec="none"))


__all__ = ["BIN_COLORS", "BIN_TEXT", "SURFACE", "INK", "INK_2", "MUTED", "GRID", "BASELINE", "DPI",
           "apply_theme", "bin_color", "style_axes", "header", "zero_is_sp500", "footnote", "bin_scale", "chip",
           "FancyBboxPatch"]
