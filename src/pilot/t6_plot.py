"""T6: one graph per firm - next-year return after each 10-K, colored by change bin."""
from __future__ import annotations

import logging

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.ticker import FuncFormatter, MaxNLocator  # noqa: E402

from pilot.config import Config, write_report  # noqa: E402

log = logging.getLogger("pilot.t6_plot")

BIN_COLORS = {1: "#e41a1c", 2: "#ff9900", 3: "#f2d600", 4: "#a6e22e", 5: "#1a9e1a"}
SPY_COLOR = "#b0b0b0"
OUTLINE = "#333333"
INK = "#222222"
MUTED = "#666666"
FOOTNOTE_TEMPLATE = ("Bins rank the 5 pilot firms within each year on cosine similarity of {sections} to the prior-year 10-K. "
            "The first filing (FY2020) is the comparison base and is not plotted.")
SECTION_SHORT = {"risk_factors": "Risk Factors (Item 1A)", "mdna": "MD&A (Item 7)"}
FOOTNOTE = FOOTNOTE_TEMPLATE.format(sections=" + ".join(SECTION_SHORT.values()))
FIGSIZE = (8, 4.5)
DPI = 200


def bin_color(b: int) -> str:
    return BIN_COLORS[int(b)]


def legend_handles() -> list[Line2D]:
    labels = {1: "Q1 = largest change in 10-K", 2: "Q2", 3: "Q3", 4: "Q4", 5: "Q5 = smallest change"}
    hs = [Line2D([], [], color=BIN_COLORS[b], lw=2, marker="o", ms=7, mfc=BIN_COLORS[b],
                 mec=OUTLINE, mew=0.6, label=labels[b]) for b in range(1, 6)]
    hs.append(Line2D([], [], color=SPY_COLOR, lw=2, label="S&P 500 (SPY)"))
    return hs


def plot_firm(ticker: str, df: pd.DataFrame, out_path, footnote: str = FOOTNOTE):
    """df: one firm's rows with filing_date, bin, firm_return_pct, spy_return_pct, partial, window_end."""
    df = df.sort_values("filing_date").reset_index(drop=True)
    x = pd.to_datetime(df["filing_date"]).dt.year.to_numpy()
    y = df["firm_return_pct"].to_numpy()

    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    fig.subplots_adjust(left=0.09, right=0.97, top=0.9, bottom=0.27)
    ax.axhline(0, color="#d9d9d9", lw=1, zorder=1)
    ax.grid(axis="y", color="#eeeeee", lw=0.8, zorder=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#bbbbbb")

    ax.plot(x, df["spy_return_pct"], color=SPY_COLOR, lw=2, marker="o", ms=4, zorder=2)

    # Firm line: each segment takes the color of the bin at its later end point.
    for i in range(1, len(df)):
        ax.plot(x[i - 1:i + 1], y[i - 1:i + 1], color=bin_color(df.loc[i, "bin"]), lw=2,
                solid_capstyle="round", zorder=3)

    span = max(y.max(), df["spy_return_pct"].max()) - min(y.min(), df["spy_return_pct"].min())
    pad = max(span, 10) * 0.06
    for i, r in df.iterrows():
        c = bin_color(r["bin"])
        # Put text on the side away from the S&P point so it never sits on the gray line.
        up = y[i] >= r["spy_return_pct"]
        sign, va = (1, "bottom") if up else (-1, "top")
        ax.annotate(f"Q{int(r['bin'])}", (x[i], y[i]), xytext=(0, 8 * sign), textcoords="offset points",
                    ha="center", va=va, fontsize=7.5, fontweight="bold", color=INK, zorder=5)
        if r["partial"]:
            ax.plot(x[i], y[i], marker="o", ms=9, mfc="white", mec=c, mew=2.2, zorder=4)
            ax.plot(x[i], y[i], marker="o", ms=11.2, mfc="none", mec=OUTLINE, mew=0.6, zorder=4)
            ax.annotate(f"through {pd.Timestamp(r['window_end']):%b %Y}", (x[i], y[i]),
                        xytext=(0, 19 * sign), textcoords="offset points", ha="center", va=va,
                        fontsize=7, color=MUTED, style="italic", zorder=5)
        else:
            ax.plot(x[i], y[i], marker="o", ms=9, mfc=c, mec=OUTLINE, mew=0.6, zorder=4)

    lo = min(y.min(), df["spy_return_pct"].min(), 0)
    hi = max(y.max(), df["spy_return_pct"].max(), 0)
    # Headroom for the Q label plus the "through ..." note above or below the extreme points.
    ax.set_ylim(lo - 4 * pad, hi + 4 * pad)
    ax.set_xlim(x.min() - 0.4, x.max() + 0.4)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xticks(range(int(x.min()), int(x.max()) + 1))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.set_xlabel("Filing year", fontsize=9, color=INK)
    ax.set_ylabel("Return (%)", fontsize=9, color=INK)
    ax.set_title(f"{ticker}: Yearly Return After 10-K Filing", fontsize=12, color=INK, loc="left",
                 fontweight="bold")

    fig.legend(handles=legend_handles(), loc="lower center", bbox_to_anchor=(0.5, 0.075), ncol=6,
               frameon=False, fontsize=7, handlelength=1.8, columnspacing=1.1, handletextpad=0.5)
    fig.text(0.5, 0.02, footnote, ha="center", va="bottom", fontsize=6.2, color=MUTED, wrap=True)
    fig.savefig(out_path, dpi=DPI)
    plt.close(fig)
    return out_path


def run_plot(cfg: Config) -> list:
    from pilot.cli import CheckFailed

    p = cfg.paths
    p.figures.mkdir(parents=True, exist_ok=True)
    sim = pd.read_parquet(p.similarity)[["ticker", "fy", "bin", "cosine_sim"]]
    ret = pd.read_parquet(p.returns)
    df = ret.merge(sim, on=["ticker", "fy"], how="inner", validate="one_to_one")
    first_fy = min(cfg.fiscal_years)
    footnote = FOOTNOTE_TEMPLATE.replace("FY2020", f"FY{first_fy}").format(
        sections=" + ".join(SECTION_SHORT[s] for s in cfg.sections))
    paths, points = [], {}
    for t in cfg.tickers:
        g = df[df["ticker"] == t]
        if g.empty:
            log.warning("no scored rows for %s; no figure", t)
            continue
        out = p.figures / f"{t}_yearly_returns.png"
        plot_firm(t, g, out, footnote)
        paths.append(out)
        points[t] = len(g)
        log.info("wrote %s (%d points)", out.relative_to(p.root), len(g))
    write_report(cfg, "plot", {"figures": [str(x.relative_to(p.root)) for x in paths], "points": points})
    print(f"\n[T6 check] figures written: {len(paths)} / {len(cfg.tickers)}; points per firm: {points}")
    if len(paths) != len(cfg.tickers):
        raise CheckFailed("missing figures")
    return paths
