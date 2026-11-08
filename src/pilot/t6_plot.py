"""T6: the graphics.

1. One graph per firm: a bar per 10-K showing the firm's return minus the S&P 500 over
   the 12 months after the filing, filled with the filing's change-bin color, a Q badge
   under each year, and a header with the firm's record against the market.
2. pooled_by_bin.png: every firm-year with a full window, grouped by bin, with each bin's
   mean and 95% confidence interval and the Q5 - Q1 spread.
3. all_firms_heatmap.png: every firm x filing year in one grid; cell color = bin,
   cell text = return vs the S&P 500.
4. all_firms_combined.png: all firms combined into five equal-weighted bin baskets, each
   compounded year by year against the S&P 500 over the same windows.

Bars start at 0 = the S&P 500, since every number is already measured against it. Each
filing is a separate 12-month holding, so bars (not a connecting line) are used per firm.
"""
from __future__ import annotations

import logging
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
from matplotlib.transforms import blended_transform_factory  # noqa: E402
from scipy import stats  # noqa: E402

from pilot.config import Config, write_report  # noqa: E402
from pilot.style import (  # noqa: E402
    BASELINE, BIN_COLORS, BIN_TEXT, DPI, GRID, INK, INK_2, MUTED, SURFACE,
    apply_theme, bin_color, bin_scale, chip, footnote, header, style_axes, zero_is_sp500,
)

log = logging.getLogger("pilot.t6_plot")

SECTION_SHORT = {"risk_factors": "Risk Factors (Item 1A)", "mdna": "MD&A (Item 7)"}
FIGSIZE = (8, 4.5)
BIN_WORDS = {1: "most\nchanged", 2: "", 3: "typical", 4: "", 5: "least\nchanged"}

__all__ = ["BIN_COLORS", "bin_color", "plot_firm", "bin_summary", "q5_minus_q1", "plot_pooled",
           "plot_heatmap", "bin_baskets", "plot_combined", "run_plot"]


_pp = zero_is_sp500(lambda v: f"{v:+.0f} pp")


def _signed(v: float) -> str:
    r = int(round(v))
    return f"{r:+d}".replace("-", "−") if r else "0"


def basis_note(cfg: Config) -> str:
    sections = " + ".join(SECTION_SHORT[s] for s in cfg.sections)
    first = min(cfg.fiscal_years)
    hist = [first + 1 + i for i in range(cfg.relative_min_history)]
    span = f"FY{hist[0]}" + (f"–FY{hist[-1]}" if len(hist) > 1 else "")
    return (f"Change = 1 − cosine similarity of {sections} to the prior-year 10-K, divided by the firm's own "
            f"median change in earlier years. Bins rank all {len(cfg.firms)} firms within each year.\n"
            f"FY{first} is the comparison base and {span} build each firm's history, so the first bin is FY{hist[-1] + 1}.")


# --------------------------------------------------------------------------- 1. per firm


def plot_firm(firm: dict, df: pd.DataFrame, out_path, note: str = ""):
    """firm: {ticker, name, sector}. df: that firm's rows with filing_date, bin,
    excess_return_pct, partial, window_end. Rows without a bin are skipped."""
    apply_theme()
    df = df[df["bin"].notna()].sort_values("filing_date").reset_index(drop=True)
    x = pd.to_datetime(df["filing_date"]).dt.year.to_numpy()
    y = df["excess_return_pct"].to_numpy(float)
    full = df[~df["partial"]]

    fig = plt.figure(figsize=FIGSIZE, dpi=DPI)
    ax = fig.add_axes([0.085, 0.32, 0.88, 0.45])
    style_axes(ax)

    for xi, yi, b, part in zip(x, y, df["bin"], df["partial"]):
        ax.bar(xi, yi, width=0.62, color=bin_color(b), edgecolor=SURFACE, linewidth=1.2, zorder=3,
               hatch="////" if part else None, alpha=0.78 if part else 1.0)
        off, va = (3, "bottom") if yi >= 0 else (-3, "top")
        ax.annotate(_signed(yi), (xi, yi), xytext=(0, off), textcoords="offset points", ha="center",
                    va=va, fontsize=7.5, color=INK, fontweight="bold", zorder=4)
    ax.axhline(0, color=BASELINE, lw=1.3, zorder=5)

    lo, hi = min(y.min(), 0), max(y.max(), 0)
    pad = max(hi - lo, 10) * 0.14
    ax.set_ylim(lo - pad, hi + pad)
    ax.set_xlim(x.min() - 0.55, x.max() + 0.45)
    ax.set_xticks(x)
    ax.set_xticklabels([str(v) for v in x], fontsize=8, color=INK_2)
    ax.yaxis.set_major_formatter(FuncFormatter(_pp))
    tr = blended_transform_factory(ax.transData, ax.transAxes)
    for xi, b, part, end in zip(x, df["bin"], df["partial"], df["window_end"]):
        chip(ax, xi, -0.15, int(b), tr)
        if part:
            ax.annotate(f"thru {pd.Timestamp(end):%b '%y}", (xi, -0.25), xycoords=tr, ha="center",
                        va="center", fontsize=6.3, color=MUTED, style="italic", annotation_clip=False)

    beat = int((full["excess_return_pct"] > 0).sum())
    detail = ""
    if len(full):
        best = full.loc[full["excess_return_pct"].idxmax()]
        worst = full.loc[full["excess_return_pct"].idxmin()]
        detail = (f"Average {_signed(full['excess_return_pct'].mean())} pp a year  ·  best {_signed(best['excess_return_pct'])} pp "
                  f"({pd.Timestamp(best['filing_date']).year})  ·  worst {_signed(worst['excess_return_pct'])} pp "
                  f"({pd.Timestamp(worst['filing_date']).year})  ·  full 12-month windows only")
    header(fig, f"{firm['ticker']}", f"{firm['name']}  ·  {firm['sector']}  ·  return minus the S&P 500 "
           "in the 12 months after each 10-K, by filing year",
           headline=f"Beat the S&P 500 in {beat} of {len(full)} full years", detail=detail)
    bin_scale(fig, 0.06, 0.62, partial=bool(df["partial"].any()))
    footnote(fig, note)
    fig.savefig(out_path, dpi=DPI)
    plt.close(fig)
    return out_path


# --------------------------------------------------------------------------- 2. pooled


def bin_summary(df: pd.DataFrame, bin_col: str, value: str = "excess_return_pct") -> pd.DataFrame:
    """Per bin: n, mean, sd, share beating the S&P 500, and a two-sided 95% t interval."""
    rows = []
    for b in range(1, 6):
        v = df.loc[df[bin_col] == b, value].dropna().to_numpy(float)
        n = len(v)
        mean = float(v.mean()) if n else math.nan
        sd = float(v.std(ddof=1)) if n > 1 else math.nan
        half = float(stats.t.ppf(0.975, n - 1) * sd / math.sqrt(n)) if n > 1 else math.nan
        rows.append({"bin": b, "n": n, "mean": mean, "sd": sd, "ci_low": mean - half, "ci_high": mean + half,
                     "share_beat": float((v > 0).mean()) if n else math.nan})
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


def _spread_offsets(n: int, width: float = 0.27) -> np.ndarray:
    """Deterministic, evenly filled horizontal offsets (van der Corput) so dots do not stack."""
    out = []
    for i in range(1, n + 1):
        v, denom, k = 0.0, 1.0, i
        while k:
            denom *= 2
            k, r = divmod(k, 2)
            v += r / denom
        out.append((v - 0.5) * 2 * width)
    return np.array(out)


def plot_pooled(df: pd.DataFrame, out_path, bin_col: str = "bin", note: str = "", n_firms: int | None = None):
    """df: one row per firm-year with excess_return_pct and `bin_col`. Returns (summary, spread)."""
    apply_theme()
    summ, spread = bin_summary(df, bin_col), q5_minus_q1(df, bin_col)
    fig = plt.figure(figsize=FIGSIZE, dpi=DPI)
    ax = fig.add_axes([0.085, 0.32, 0.88, 0.45])
    style_axes(ax)
    y = df["excess_return_pct"]
    pad = (y.max() - y.min()) * 0.07
    for b in range(1, 6):
        v = df.loc[df[bin_col] == b].sort_values("excess_return_pct")["excess_return_pct"].to_numpy(float)
        s = summ.loc[summ["bin"] == b].iloc[0]
        if s["n"] > 1:
            ax.add_patch(Rectangle((b - 0.34, s["ci_low"]), 0.68, s["ci_high"] - s["ci_low"],
                                   color=BIN_COLORS[b], alpha=0.16, lw=0, zorder=1))
        ax.scatter(b + _spread_offsets(len(v)), v, s=15, color=BIN_COLORS[b], alpha=0.75, lw=0, zorder=2)
        if s["n"]:
            ax.plot([b - 0.34, b + 0.34], [s["mean"]] * 2, color=INK, lw=2.2, solid_capstyle="butt", zorder=4)
            ax.annotate(f"{_signed(s['mean'])}", (b + 0.36, s["mean"]), xytext=(2, 0), textcoords="offset points",
                        va="center", ha="left", fontsize=7.5, fontweight="bold", color=INK, zorder=5)
    ax.axhline(0, color=BASELINE, lw=1.3, zorder=3)
    ax.set_xlim(0.5, 5.7)
    ax.set_ylim(y.min() - pad, y.max() + pad)
    ax.set_xticks([])
    ax.yaxis.set_major_formatter(FuncFormatter(_pp))
    tr = blended_transform_factory(ax.transData, ax.transAxes)
    for b in range(1, 6):
        s = summ.loc[summ["bin"] == b].iloc[0]
        chip(ax, b, -0.07, b, tr, fontsize=7.5)
        words = BIN_WORDS[b].replace("\n", " ")
        line = f"{words}\n" if words else "\n"
        ax.annotate(f"{line}n = {int(s['n'])}  ·  {s['share_beat']:.0%} beat", (b, -0.14), xycoords=tr,
                    ha="center", va="top", fontsize=6.6, color=INK_2, annotation_clip=False, linespacing=1.35)

    years = sorted(df["fy"].unique())
    firms = n_firms or df["ticker"].nunique()
    headline, detail = "", ""
    if not math.isnan(spread["diff"]):
        headline = f"Q5 − Q1 spread: {_signed(spread['diff'])} pp"
        detail = (f"Dots = filings  ·  black bar = bin mean  ·  shaded band = 95% CI  ·  "
                  f"Q5 − Q1 95% CI {_signed(spread['ci_low'])} to {_signed(spread['ci_high'])} pp, p = {spread['p']:.2f}")
    header(fig, "Do bigger rewrites lead to a weaker year?",
           f"All {firms} firms, FY{years[0]}–FY{years[-1]} 10-Ks: return minus the S&P 500 in the 12 months "
           "after each filing, by change bin", headline=headline, detail=detail)
    footnote(fig, note)
    fig.savefig(out_path, dpi=DPI)
    plt.close(fig)
    return summ, spread


# --------------------------------------------------------------------------- 3. heatmap


def plot_heatmap(df: pd.DataFrame, firms: list[dict], out_path, note: str = ""):
    """Rows = firms grouped by sector, columns = filing years. Cell = bin color + return vs S&P."""
    apply_theme()
    df = df[df["bin"].notna()].copy()
    df["year"] = pd.to_datetime(df["filing_date"]).dt.year
    years = sorted(df["year"].unique())
    order = sorted(firms, key=lambda f: (f["sector"], f["ticker"]))
    n_rows = len(order)
    height = 1.75 + 0.3 * n_rows
    fig = plt.figure(figsize=(8, height), dpi=DPI)
    top_in, bottom_in = 1.3, 0.85
    ax = fig.add_axes([0.27, bottom_in / height, 0.6, 1 - (top_in + bottom_in) / height])
    ax.set_xlim(-0.5, len(years) - 0.5)
    ax.set_ylim(n_rows - 0.5, -0.5)
    ax.axis("off")
    cells = df.set_index(["ticker", "year"])
    prev_sector = None
    for r, f in enumerate(order):
        if f["sector"] != prev_sector:
            ax.annotate(f["sector"], (-0.5, r), xytext=(-62, 0), textcoords="offset points", ha="right",
                        va="center", fontsize=6.6, color=MUTED, annotation_clip=False)
            if prev_sector is not None:
                ax.plot([-3.2, len(years) + 0.9], [r - 0.5, r - 0.5], color=GRID, lw=0.8, clip_on=False)
            prev_sector = f["sector"]
        ax.annotate(f["ticker"], (-0.5, r), xytext=(-8, 0), textcoords="offset points", ha="right",
                    va="center", fontsize=8, fontweight="bold", color=INK, annotation_clip=False)
        full_vals = []
        for c, yr in enumerate(years):
            if (f["ticker"], yr) not in cells.index:
                continue
            row = cells.loc[(f["ticker"], yr)]
            b = int(row["bin"])
            ax.add_patch(Rectangle((c - 0.46, r - 0.42), 0.92, 0.84, color=BIN_COLORS[b], lw=0,
                                   hatch="////" if row["partial"] else None, alpha=0.78 if row["partial"] else 1))
            ax.text(c, r, _signed(row["excess_return_pct"]), ha="center", va="center", fontsize=7,
                    color=BIN_TEXT[b], fontweight="bold")
            if not row["partial"]:
                full_vals.append(row["excess_return_pct"])
        if full_vals:
            m = float(np.mean(full_vals))
            ax.text(len(years) - 0.5 + 0.55, r, _signed(m), ha="center", va="center", fontsize=7.5,
                    color=INK if m >= 0 else INK_2, fontweight="bold")
    for c, yr in enumerate(years):
        part = df[(df["year"] == yr)]["partial"].any()
        ax.text(c, -0.85, f"{yr}" + ("*" if part else ""), ha="center", va="bottom", fontsize=7.5, color=INK_2)
    ax.text(len(years) - 0.5 + 0.55, -0.85, "avg", ha="center", va="bottom", fontsize=7.5, color=INK_2,
            fontweight="bold")
    partial_end = df.loc[df["partial"], "window_end"]
    star = (f"  * window still open, measured through {pd.Timestamp(partial_end.max()):%b %Y}; left out of the average."
            if len(partial_end) else "")
    header(fig, "Every firm, every year",
           "Return minus the S&P 500 in the 12 months after each 10-K (pp), colored by change bin. Columns are filing years.",
           top_in=0.2)
    bin_scale(fig, 0.06, 0.55, partial=bool(len(partial_end)))
    footnote(fig, (note + star).strip(), y_in=0.1)
    fig.savefig(out_path, dpi=DPI)
    plt.close(fig)
    return out_path


# --------------------------------------------------------------------------- 4. combined


def bin_baskets(df: pd.DataFrame, bin_col: str = "bin") -> pd.DataFrame:
    """For each filing year and bin: an equal-weighted basket of that bin's firms, held for
    each firm's 12-month window, and the S&P 500 over the same windows. Full windows only.
    `relative` compounds basket and S&P separately and divides, so 1.10 = 10% ahead."""
    d = df[df[bin_col].notna() & ~df["partial"]].copy()
    d["year"] = pd.to_datetime(d["filing_date"]).dt.year
    g = (d.groupby(["year", bin_col])
          .agg(n=("ticker", "size"), basket=("firm_return_pct", "mean"), spy=("spy_return_pct", "mean"))
          .reset_index().rename(columns={bin_col: "bin"}).sort_values(["bin", "year"]))
    g["_b"], g["_s"] = 1 + g["basket"] / 100, 1 + g["spy"] / 100
    g["relative"] = g.groupby("bin")["_b"].cumprod() / g.groupby("bin")["_s"].cumprod()
    g = g.drop(columns=["_b", "_s"])
    return g.reset_index(drop=True)


def plot_combined(baskets: pd.DataFrame, out_path, note: str = "", n_firms: int = 0):
    apply_theme()
    fig = plt.figure(figsize=FIGSIZE, dpi=DPI)
    ax = fig.add_axes([0.085, 0.22, 0.72, 0.53])
    style_axes(ax)
    years = sorted(baskets["year"].unique())
    start = years[0] - 1
    ends = {}
    for b in [3, 2, 4, 1, 5]:  # extremes drawn last, on top
        t = baskets[baskets["bin"] == b].sort_values("year")
        xs = [start] + t["year"].tolist()
        ys = [0.0] + ((t["relative"] - 1) * 100).tolist()
        strong = b in (1, 5)
        ax.plot(xs, ys, color=BIN_COLORS[b], lw=2.6 if strong else 1.4, alpha=1 if strong else 0.85,
                zorder=4 if strong else 3, solid_capstyle="round")
        ax.scatter(xs[-1], ys[-1], s=34 if strong else 18, color=BIN_COLORS[b], zorder=5, lw=0)
        ends[b] = ys[-1]
    ax.axhline(0, color=BASELINE, lw=1.3, zorder=2)
    ax.yaxis.set_major_formatter(FuncFormatter(zero_is_sp500(lambda v: f"{v:+.0f}%")))
    ax.set_xticks([start] + years)
    ax.set_xticklabels(["start"] + [str(y) for y in years], fontsize=8)
    ax.set_xlim(start - 0.2, years[-1] + 0.2)

    # Direct labels at the line ends, pushed apart so they never overlap.
    lo, hi = ax.get_ylim()
    gap = (hi - lo) * 0.075
    placed = {}
    for b, v in sorted(ends.items(), key=lambda kv: kv[1]):
        y = v
        if placed:
            y = max(y, max(placed.values()) + gap)
        placed[b] = y
    shift = max(0.0, max(placed.values()) - (hi - gap * 0.3))
    for b, y in placed.items():
        words = {1: " most changed", 5: " least changed"}.get(b, "")
        ax.annotate(f"Q{b}{words}  {ends[b]:+.0f}%".replace("-", "−"), (years[-1], ends[b]),
                    xytext=(years[-1] + 0.25, y - shift), textcoords="data", ha="left", va="center",
                    fontsize=7.6, color=INK if b in (1, 5) else INK_2, fontweight="bold" if b in (1, 5) else "normal",
                    annotation_clip=False,
                    arrowprops=dict(arrowstyle="-", color=BIN_COLORS[b], lw=0.8, shrinkA=0, shrinkB=3))
    spread = ends.get(5, math.nan) - ends.get(1, math.nan)
    header(fig, "All firms combined: one basket per bin",
           f"Each year the {n_firms} firms' 10-Ks are split into 5 equal-weighted baskets by change bin. "
           "Line = cumulative return ahead of the S&P 500.",
           headline=(f"Q5 ahead of Q1 by {years[-1]}: {spread:+.0f} points".replace("-", "−")
                     if not math.isnan(spread) else ""),
           detail="Each point is after holding that filing year's baskets for 12 months. Start = level with the S&P 500.")
    footnote(fig, note)
    fig.savefig(out_path, dpi=DPI)
    plt.close(fig)
    return out_path


# --------------------------------------------------------------------------- main step


def run_plot(cfg: Config) -> list:
    from pilot.cli import CheckFailed

    p = cfg.paths
    p.figures.mkdir(parents=True, exist_ok=True)
    for old in p.figures.glob("*.png"):  # firms removed from config should not leave stale files
        old.unlink()
    sim = pd.read_parquet(p.similarity)
    ret = pd.read_parquet(p.returns)
    cols = ["ticker", "fy", "bin", "bin_raw", "cosine_sim", "rel_change"]
    df = ret.merge(sim[[c for c in cols if c in sim.columns]], on=["ticker", "fy"], how="inner",
                   validate="one_to_one")
    firms = [{"ticker": f.ticker, "name": f.name, "sector": f.sector} for f in cfg.firms]
    note = basis_note(cfg)

    paths, points = [], {}
    for f in firms:
        g = df[(df["ticker"] == f["ticker"]) & df["bin"].notna()]
        if g.empty:
            log.warning("no binned rows for %s; no figure", f["ticker"])
            continue
        out = p.figures / f"{f['ticker']}_yearly_returns.png"
        plot_firm(f, g, out, note)
        paths.append(out)
        points[f["ticker"]] = len(g)

    pool = df[~df["partial"] & df["bin"].notna()].copy()
    years = sorted(pool["fy"].unique())
    pooled_note = (f"n = {len(pool)} firm-years ({len(cfg.firms)} firms × {len(years)} years); partial windows "
                   f"(FY{max(cfg.fiscal_years)}) are left out. The 95% intervals treat filings as independent, which "
                   "overstates precision\nwhen firms move together in the same year. "
                   f"{len(cfg.firms)} hand-picked large firms illustrate the method; this is not a test of the Lazy Prices effect.")
    summ, spread = plot_pooled(pool, p.figures / "pooled_by_bin.png", "bin", pooled_note, len(cfg.firms))
    raw_summ, raw_spread = bin_summary(pool, "bin_raw"), q5_minus_q1(pool, "bin_raw")
    paths.append(p.figures / "pooled_by_bin.png")

    paths.append(plot_heatmap(df, firms, p.figures / "all_firms_heatmap.png", note))

    baskets = bin_baskets(df)
    baskets.to_csv(p.data / "bin_baskets.csv", index=False)
    combined_note = ("Each firm is held from the month-end after its 10-K for 12 months; the S&P 500 is measured over "
                     "the same windows. Baskets are rebuilt every filing year;\nwindows overlap by a few weeks "
                     f"because filing dates differ. Full windows only (filing years {int(baskets['year'].min())}–"
                     f"{int(baskets['year'].max())}). Illustrative, not a trading strategy test.")
    paths.append(plot_combined(baskets, p.figures / "all_firms_combined.png", combined_note, len(cfg.firms)))

    pd.concat([summ.assign(basis="bin"), raw_summ.assign(basis="bin_raw")]).to_csv(
        p.data / "pooled_by_bin.csv", index=False)
    final = baskets.sort_values("year").groupby("bin").tail(1).set_index("bin")["relative"]
    write_report(cfg, "plot", {
        "figures": [str(x.relative_to(p.root)) for x in paths], "points": points,
        "pooled_n": len(pool), "pooled_years": [int(y) for y in years],
        "pooled": {"bin": {"spread_q5_minus_q1": spread, "by_bin": summ.round(3).to_dict("records")},
                   "bin_raw": {"spread_q5_minus_q1": raw_spread, "by_bin": raw_summ.round(3).to_dict("records")}},
        "baskets_final_relative": {int(b): round(float(v), 4) for b, v in final.items()},
        "baskets_years": [int(baskets["year"].min()), int(baskets["year"].max())],
    })
    n_expected = len(cfg.tickers) + 3
    print(f"\n[T6 check] figures written: {len(paths)} ({len(points)} firms + pooled + heatmap + combined); "
          f"points per firm: {points}")
    print(f"\n[T6] pooled return vs S&P 500 by bin (n = {len(pool)}):")
    print(summ.round(2).to_string(index=False))
    print(f"Q5 - Q1 = {spread['diff']:+.1f} pp, 95% CI {spread['ci_low']:+.1f} to {spread['ci_high']:+.1f}, "
          f"p = {spread['p']:.2f}  (raw-similarity bins: {raw_spread['diff']:+.1f} pp, p = {raw_spread['p']:.2f})")
    print(f"[T6] baskets, cumulative vs S&P 500 by {int(baskets['year'].max())}: "
          + ", ".join(f"Q{b} {(v - 1) * 100:+.0f}%" for b, v in final.items()))
    if len(paths) != n_expected:
        raise CheckFailed(f"expected {n_expected} figures, wrote {len(paths)}")
    return paths
