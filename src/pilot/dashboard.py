"""Data for the Streamlit dashboard (app.py).

The dashboard reads the same files the pipeline writes (data/similarity.parquet and
data/returns.parquet) and reuses the pipeline's own statistics (t6_plot), so every number
on the site matches the PNGs and outputs/coverage.txt.
"""
from __future__ import annotations

import pandas as pd

from pilot.config import Config
from pilot.t6_plot import bin_baskets, bin_summary, q5_minus_q1

# Bin columns the viewer can rank by. bin_relative is the project's main choice.
BASES = {"bin_relative": "Change vs the firm's own past years", "bin_raw": "Raw similarity"}
BIN_WORDS = {1: "most changed", 2: "", 3: "typical", 4: "", 5: "least changed"}

FIRM_YEAR_COLUMNS = ["ticker", "name", "sector", "fy", "filing_year", "filing_date", "window_start",
                     "window_end", "partial", "bin_relative", "bin_raw", "cosine_sim", "change",
                     "rel_change", "firm_return_pct", "spy_return_pct", "excess_return_pct"]


def firm_years(cfg: Config) -> pd.DataFrame:
    """One row per filing that has a firm-relative bin (the filings every chart uses)."""
    p = cfg.paths
    sim = pd.read_parquet(p.similarity)
    ret = pd.read_parquet(p.returns)
    keep = ["ticker", "fy", "bin_relative", "bin_raw", "cosine_sim", "change", "rel_change"]
    df = ret.merge(sim[keep], on=["ticker", "fy"], how="inner", validate="one_to_one")
    info = pd.DataFrame([{"ticker": f.ticker, "name": f.name, "sector": f.sector} for f in cfg.firms])
    df = df.merge(info, on="ticker", how="left", validate="many_to_one")
    df = df[df["bin_relative"].notna()].copy()
    for c in ("bin_relative", "bin_raw"):
        df[c] = df[c].astype(int)
    df["filing_year"] = pd.to_datetime(df["filing_date"]).dt.year
    return df[FIRM_YEAR_COLUMNS].sort_values(["ticker", "fy"]).reset_index(drop=True)


def pooled(df: pd.DataFrame, bin_col: str) -> tuple[pd.DataFrame, dict]:
    """Bin means with 95% CIs, and B5 - B1 with a Welch test. Full 12-month windows only,
    the same rows as pooled_by_bin.png."""
    full = df[~df["partial"]]
    return bin_summary(full, bin_col), q5_minus_q1(full, bin_col)


def baskets(df: pd.DataFrame, bin_col: str) -> pd.DataFrame:
    """Cumulative basket returns ahead of the S&P 500, one line per bin, with a starting row
    at 0 so every line begins level with the market. Same method as all_firms_combined.png."""
    b = bin_baskets(df, bin_col)
    b["ahead_pct"] = (b["relative"] - 1) * 100
    start = pd.DataFrame({"bin": range(1, 6), "window_end": b["window_start"].min(), "ahead_pct": 0.0})
    return pd.concat([start, b[["bin", "year", "n", "window_end", "ahead_pct"]]], ignore_index=True)
