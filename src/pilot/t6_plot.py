"""T6: one graph per firm, plus one pooled graph of next-year return by change bin.

Per firm: the firm's 12-month return after each 10-K, colored by change bin. With
plot_return: excess (default) the y axis is the return minus the S&P 500 over the same
window, so the S&P 500 is the flat gray line at 0. With plot_return: raw it is the original
look: firm return and S&P 500 return as two lines.

Pooled: every firm-year with a full 12-month window, grouped by bin, with each bin's mean
and 95% confidence interval. Two panels on the same filings and y axis: bins on the
firm-relative change score and bins on raw similarity, so the two can be compared.
"""
from __future__ import annotations

import logging
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
from scipy import stats  # noqa: E402

from pilot.config import Config, write_report  # noqa: E402

log = logging.getLogger("pilot.t6_plot")

BIN_COLORS = {1: "#e41a1c", 2: "#ff9900", 3: "#f2d600", 4: "#a6e22e", 5: "#1a9e1a"}
SPY_COLOR = "#b0b0b0"
OUTLINE = "#333333"
INK = "#222222"
MUTED = "#666666"
SECTION_SHORT = {"risk_factors": "Risk Factors (Item 1A)", "mdna": "MD&A (Item 7)"}
FIGSIZE = (8, 4.5)
DPI = 200


def bin_color(b: int) -> str:
    return BIN_COLORS[int(b)]


def _pp(v, _=None) -> str:
    return f"{v:+.0f} pp" if v else "0"


def _style(ax) -> None:
    ax.grid(axis="y", color="#eeeeee", lw=0.8, zorder=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#bbbbbb")
    ax.tick_params(colors=MUTED, labelsize=8)


def legend_handles(mode: str = "excess") -> list[Line2D]:
    labels = {1: "Q1 = largest change in 10-K", 2: "Q2", 3: "Q3", 4: "Q4", 5: "Q5 = smallest change"}
    hs = [Line2D([], [], color=BIN_COLORS[b], lw=2, marker="o", ms=7, mfc=BIN_COLORS[b],
                 mec=OUTLINE, mew=0.6, label=labels[b]) for b in range(1, 6)]
    spy = "S&P 500 (= 0)" if mode == "excess" else "S&P 500 (SPY)"
    hs.append(Line2D([], [], color=SPY_COLOR, lw=2, label=spy))
    return hs


def footnote_text(cfg: Config) -> str:
    sections = " + ".join(SECTION_SHORT[s] for s in cfg.sections)
    first = min(cfg.fiscal_years)
    if cfg.bin_basis == "firm_relative":
        build = [first + 1 + i for i in range(cfg.relative_min_history)]
        span = f"FY{build[0]}" + (f"-FY{build[-1]}" if len(build) > 1 else "")
        return (f"Bins rank the {len(cfg.firms)} pilot firms within each year on how much {sections} changed vs the "
                f"prior-year 10-K, relative to the firm's own median change\nin earlier years. "
                f"FY{first} is the comparison base and {span} build each firm's history, so they are not plotted.")
    return (f"Bins rank the {len(cfg.firms)} pilot firms within each year on cosine similarity of {sections} "
            f"to the prior-year 10-K.\nThe first filing (FY{first}) is the comparison base and is not plotted.")


# --------------------------------------------------------------------------- per firm


def plot_firm(ticker: str, df: pd.DataFrame, out_path, footnote: str = "", mode: str = "excess"):
    """df: one firm's rows with filing_date, bin, firm_return_pct, spy_return_pct,
    excess_return_pct, partial, window_end. Rows without a bin are skipped."""
    df = df[df["bin"].notna()].sort_values("filing_date").reset_index(drop=True)
    x = pd.to_datetime(df["filing_date"]).dt.year.to_numpy()
    if mode == "excess":
        y = df["excess_return_pct"].to_numpy()
        ref = np.zeros(len(df))
    else:
        y = df["firm_return_pct"].to_numpy()
        ref = df["spy_return_pct"].to_numpy()

    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    fig.subplots_adjust(left=0.1, right=0.97, top=0.9, bottom=0.29)
    _style(ax)
    if mode == "excess":
        ax.axhline(0, color=SPY_COLOR, lw=2, zorder=2)
    else:
        ax.axhline(0, color="#d9d9d9", lw=1, zorder=1)
        ax.plot(x, ref, color=SPY_COLOR, lw=2, marker="o", ms=4, zorder=2)

    # Firm line: each segment takes the color of the bin at its later end point.
    for i in range(1, len(df)):
        ax.plot(x[i - 1:i + 1], y[i - 1:i + 1], color=bin_color(df.loc[i, "bin"]), lw=2,
                solid_capstyle="round", zorder=3)

    for i, r in df.iterrows():
        c = bin_color(r["bin"])
        # Text goes on the side away from the S&P 500 so it never sits on the gray line.
        sign, va = (1, "bottom") if y[i] >= ref[i] else (-1, "top")
        ax.annotate(f"Q{int(r['bin'])}", (x[i], y[i]), xytext=(0, 8 * sign), textcoords="offset points",
                    ha="center", va=va, fontsize=7.5, fontweight="bold", color=INK, zorder=5)
        if r["partial"]:
            ax.plot(x[i], y[i], marker="o", ms=9, mfc="white", mec=c, mew=2.2, zorder=4)
            ax.plot(x[i], y[i], marker="o", ms=11.2, mfc="none", mec=OUTLINE, mew=0.6, zorder=4)
            ax.annotate(f"through {pd.Timestamp(r['window_end']):%b %Y}", (x[i], y[i]),
                        xytext=(0, 19 * sign), textcoords="offset points", ha="center", va=va,
                        fontsize=7, color=MUTED, style="italic", zorder=6,
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.9))
        else:
            ax.plot(x[i], y[i], marker="o", ms=9, mfc=c, mec=OUTLINE, mew=0.6, zorder=4)

    lo, hi = min(y.min(), ref.min(), 0), max(y.max(), ref.max(), 0)
    pad = max(hi - lo, 10) * 0.06
    ax.set_ylim(lo - 4 * pad, hi + 4 * pad)
    ax.set_xlim(x.min() - 0.4, x.max() + 0.4)
    ax.set_xticks(range(int(x.min()), int(x.max()) + 1))
    ax.set_xlabel("Filing year", fontsize=9, color=INK)
    if mode == "excess":
        ax.yaxis.set_major_formatter(FuncFormatter(_pp))
        ax.set_ylabel("Return minus S&P 500", fontsize=9, color=INK)
        title = f"{ticker}: Return vs S&P 500 in the Year After 10-K Filing"
    else:
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
        ax.set_ylabel("Return (%)", fontsize=9, color=INK)
        title = f"{ticker}: Yearly Return After 10-K Filing"
    ax.set_title(title, fontsize=12, color=INK, loc="left", fontweight="bold")

    fig.legend(handles=legend_handles(mode), loc="lower center", bbox_to_anchor=(0.5, 0.095), ncol=6,
               frameon=False, fontsize=7, handlelength=1.8, columnspacing=1.1, handletextpad=0.5)
    fig.text(0.5, 0.02, footnote, ha="center", va="bottom", fontsize=6.2, color=MUTED, linespacing=1.4)
    fig.savefig(out_path, dpi=DPI)
    plt.close(fig)
    return out_path


# --------------------------------------------------------------------------- pooled


def bin_summary(df: pd.DataFrame, bin_col: str, value: str = "excess_return_pct") -> pd.DataFrame:
    """Per bin: n, mean, sd and a two-sided 95% t confidence interval for the mean."""
    rows = []
    for b in range(1, 6):
        v = df.loc[df[bin_col] == b, value].dropna().to_numpy(float)
        n = len(v)
        mean = float(v.mean()) if n else math.nan
        sd = float(v.std(ddof=1)) if n > 1 else math.nan
        half = float(stats.t.ppf(0.975, n - 1) * sd / math.sqrt(n)) if n > 1 else math.nan
        rows.append({"bin": b, "n": n, "mean": mean, "sd": sd, "ci_low": mean - half, "ci_high": mean + half})
    return pd.DataFrame(rows)


def q5_minus_q1(df: pd.DataFrame, bin_col: str, value: str = "excess_return_pct") -> dict:
    """Least-changed minus most-changed mean, with a Welch 95% CI and p-value.
    The Lazy Prices prediction is that this is positive."""
    a = df.loc[df[bin_col] == 5, value].dropna().to_numpy(float)
    b = df.loc[df[bin_col] == 1, value].dropna().to_numpy(float)
    if len(a) < 2 or len(b) < 2:
        return {"diff": math.nan, "ci_low": math.nan, "ci_high": math.nan, "p": math.nan,
                "n5": len(a), "n1": len(b)}
    va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
    se = math.sqrt(va + vb)
    dof = (va + vb) ** 2 / (va ** 2 / (len(a) - 1) + vb ** 2 / (len(b) - 1))
    diff = float(a.mean() - b.mean())
    half = float(stats.t.ppf(0.975, dof) * se)
    p = float(2 * stats.t.sf(abs(diff) / se, dof))
    return {"diff": diff, "ci_low": diff - half, "ci_high": diff + half, "p": p, "n5": len(a), "n1": len(b)}


def plot_pooled(df: pd.DataFrame, out_path, panels: list[tuple[str, str]], footnote: str):
    """df: one row per firm-year with excess_return_pct and the bin columns named in `panels`
    ([(bin_col, panel title), ...]). Returns {bin_col: (summary, spread)}."""
    fig, axes = plt.subplots(1, len(panels), figsize=FIGSIZE, dpi=DPI, sharey=True)
    axes = np.atleast_1d(axes)
    fig.subplots_adjust(left=0.1, right=0.98, top=0.83, bottom=0.3, wspace=0.08)
    y = df["excess_return_pct"]
    pad = (y.max() - y.min()) * 0.08
    results = {}
    for ax, (col, title) in zip(axes, panels):
        _style(ax)
        ax.axhline(0, color=SPY_COLOR, lw=2, zorder=2)  # above the grid lines (zorder 1.5)
        summ, spread = bin_summary(df, col), q5_minus_q1(df, col)
        results[col] = (summ, spread)
        for b in range(1, 6):
            v = df.loc[df[col] == b].sort_values(["fy", "ticker"])["excess_return_pct"].to_numpy()
            # Deterministic spread of dots across the bin so they do not stack.
            xs = b - 0.22 + (np.arange(len(v)) + 0.5) * 0.44 / max(len(v), 1)
            ax.scatter(xs, v, s=22, color=BIN_COLORS[b], edgecolor=OUTLINE, linewidth=0.5,
                       alpha=0.9, zorder=3)
            s = summ.loc[summ["bin"] == b].iloc[0]
            if s["n"] > 1:
                ax.plot([b + 0.3] * 2, [s["ci_low"], s["ci_high"]], color=INK, lw=1.4, zorder=4)
            if s["n"]:
                ax.plot(b + 0.3, s["mean"], marker="_", ms=14, mew=2.4, color=INK, zorder=5)
                m = int(round(s["mean"]))
                ax.annotate(f"{m:+d}" if m else "0", (b + 0.3, s["mean"]), xytext=(7, 0),
                            textcoords="offset points", va="center", fontsize=6.8, color=INK)
        ax.set_xticks(range(1, 6))
        ax.set_xticklabels(["Q1\nmost\nchanged", "Q2", "Q3", "Q4", "Q5\nleast\nchanged"], fontsize=7.5)
        ax.set_xlim(0.5, 5.75)
        ax.set_ylim(y.min() - pad, y.max() + 2.2 * pad)
        ax.set_title(title, fontsize=9, color=INK, loc="left", fontweight="bold")
        if not math.isnan(spread["diff"]):
            ax.text(0.02, 0.98, f"Q5 − Q1: {spread['diff']:+.1f} pp\n95% CI {spread['ci_low']:+.0f} to "
                    f"{spread['ci_high']:+.0f}, p = {spread['p']:.2f}", transform=ax.transAxes,
                    ha="left", va="top", fontsize=7, color=INK, linespacing=1.35)
    axes[0].yaxis.set_major_formatter(FuncFormatter(_pp))
    axes[0].set_ylabel("Return minus S&P 500, next 12 months", fontsize=8.5, color=INK)
    fig.suptitle("Next-Year Return vs S&P 500, by How Much the 10-K Changed", x=0.1, ha="left",
                 fontsize=12, fontweight="bold", color=INK)
    handles = [
        Line2D([], [], ls="none", marker="o", ms=5, mfc="#999999", mec=OUTLINE, mew=0.5, label="one firm-year"),
        Line2D([], [], color=INK, lw=1.4, marker="_", ms=10, mew=2.4, label="bin mean with 95% CI"),
        Line2D([], [], color=SPY_COLOR, lw=2, label="S&P 500 (= 0)"),
    ]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.54, 0.105), ncol=3, frameon=False,
               fontsize=7.5, handletextpad=0.5, columnspacing=1.6)
    fig.text(0.5, 0.02, footnote, ha="center", va="bottom", fontsize=6.2, color=MUTED, linespacing=1.4)
    fig.savefig(out_path, dpi=DPI)
    plt.close(fig)
    return results


# --------------------------------------------------------------------------- main step


def run_plot(cfg: Config) -> list:
    from pilot.cli import CheckFailed

    p = cfg.paths
    p.figures.mkdir(parents=True, exist_ok=True)
    sim = pd.read_parquet(p.similarity)
    sim_cols = ["ticker", "fy", "bin", "bin_raw", "bin_relative", "cosine_sim", "rel_change"]
    ret = pd.read_parquet(p.returns)
    df = ret.merge(sim[[c for c in sim_cols if c in sim.columns]], on=["ticker", "fy"], how="inner",
                   validate="one_to_one")

    footnote = footnote_text(cfg)
    paths, points = [], {}
    for t in cfg.tickers:
        g = df[(df["ticker"] == t) & df["bin"].notna()]
        if g.empty:
            log.warning("no binned rows for %s; no figure", t)
            continue
        out = p.figures / f"{t}_yearly_returns.png"
        plot_firm(t, g, out, footnote, cfg.plot_return)
        paths.append(out)
        points[t] = len(g)
        log.info("wrote %s (%d points)", out.relative_to(p.root), len(g))

    # Pooled: full 12-month windows only, and only firm-years that have a firm-relative bin,
    # so both panels compare exactly the same filings.
    pool = df[~df["partial"] & df["bin_relative"].notna()].copy()
    years = sorted(pool["fy"].unique())
    pooled_note = (f"Each dot is one firm-year: FY{years[0]}-FY{years[-1]} 10-Ks, n = {len(pool)} "
                   f"({len(cfg.firms)} firms x {len(years)} years). Partial windows (FY{max(cfg.fiscal_years)}) "
                   "are left out. CIs treat filings as independent.\n"
                   f"With {len(pool) // 5} filings per bin the intervals are wide: this illustrates the method "
                   "and is not a test of the Lazy Prices effect.")
    pooled_path = p.figures / "pooled_by_bin.png"
    results = plot_pooled(pool, pooled_path, [
        ("bin_relative", "Bins on change vs firm's own history (new)"),
        ("bin_raw", "Bins on raw cosine similarity (original)"),
    ], pooled_note)
    paths.append(pooled_path)
    tables = []
    for col, (summ, _) in results.items():
        tables.append(summ.assign(basis=col))
    pd.concat(tables).to_csv(p.data / "pooled_by_bin.csv", index=False)

    pooled_report = {col: {"spread_q5_minus_q1": spread, "by_bin": summ.round(3).to_dict("records")}
                     for col, (summ, spread) in results.items()}
    write_report(cfg, "plot", {"figures": [str(x.relative_to(p.root)) for x in paths], "points": points,
                               "plot_return": cfg.plot_return, "pooled_n": len(pool),
                               "pooled_years": [int(y) for y in years], "pooled": pooled_report})
    print(f"\n[T6 check] figures written: {len(paths)} ({len(cfg.tickers)} firms + pooled); "
          f"points per firm: {points}")
    for col, (summ, spread) in results.items():
        print(f"\n[T6] pooled excess return by {col} (n = {len(pool)}):")
        print(summ.round(1).to_string(index=False))
        print(f"Q5 - Q1 = {spread['diff']:+.1f} pp, 95% CI {spread['ci_low']:+.1f} to "
              f"{spread['ci_high']:+.1f}, p = {spread['p']:.2f}")
    if len(paths) != len(cfg.tickers) + 1:
        raise CheckFailed("missing figures")
    return paths
