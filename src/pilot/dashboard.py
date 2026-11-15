"""Data for the Streamlit dashboard (app.py).

The dashboard reads the same files the pipeline writes (data/similarity.parquet and
data/returns.parquet) and reuses the pipeline's own statistics (t6_plot), so every number
on the site matches the PNGs and outputs/coverage.txt.

data/ is git-ignored, so the hosted site can't see it. `make snapshot` (python -m
pilot.dashboard) copies the few small results the app needs into app_data/, which IS
committed; the app uses it whenever data/ is missing.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

from pilot.config import Config, load_config
from pilot.t6_plot import bin_baskets, bin_summary, q5_minus_q1

SNAPSHOT_DIR = "app_data"
SNAPSHOT_TABLE = "firm_years.csv"
DATE_COLUMNS = ["filing_date", "window_start", "window_end"]

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


def snapshot_dir(cfg: Config) -> Path:
    return cfg.paths.root / SNAPSHOT_DIR


def write_snapshot(cfg: Config) -> Path:
    """Copy what the hosted app needs into app_data/: the firm-year table, the coverage
    report, the plot step's saved statistics (so the site traces to outputs) and any
    sentence diffs. Run after `make all`; commit the folder to update the website."""
    out = snapshot_dir(cfg)
    out.mkdir(exist_ok=True)
    df = firm_years(cfg)
    df.to_csv(out / SNAPSHOT_TABLE, index=False)
    for src, name in [(cfg.paths.coverage, "coverage.txt"), (cfg.paths.reports / "plot.json", "plot.json")]:
        if src.exists():
            shutil.copy(src, out / name)
    diffs = out / "diffs"
    shutil.rmtree(diffs, ignore_errors=True)
    if cfg.paths.diffs.exists():
        shutil.copytree(cfg.paths.diffs, diffs)
    meta = {"rows": len(df), "firms": int(df["ticker"].nunique()),
            "latest_window_end": str(df["window_end"].max().date())}
    (out / "snapshot.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"[snapshot] wrote {out.name}/: {meta['rows']} filings, {meta['firms']} firms, "
          f"prices through {meta['latest_window_end']}. Commit {out.name}/ to update the website.")
    return out


def read_snapshot(cfg: Config) -> pd.DataFrame:
    df = pd.read_csv(snapshot_dir(cfg) / SNAPSHOT_TABLE, parse_dates=DATE_COLUMNS)
    return df[FIRM_YEAR_COLUMNS]


def load(cfg: Config) -> tuple[pd.DataFrame, str]:
    """The pipeline's own output when it is on this computer, else the committed snapshot.
    Returns (table, source) where source is "pipeline" or "snapshot"."""
    if cfg.paths.similarity.exists() and cfg.paths.returns.exists():
        return firm_years(cfg), "pipeline"
    if (snapshot_dir(cfg) / SNAPSHOT_TABLE).exists():
        return read_snapshot(cfg), "snapshot"
    raise FileNotFoundError("no pipeline output (run `make all`) and no app_data/ snapshot")


def coverage_text(cfg: Config) -> str | None:
    for p in (cfg.paths.coverage, snapshot_dir(cfg) / "coverage.txt"):
        if p.exists():
            return p.read_text()
    return None


def diff_files(cfg: Config, ticker: str) -> list[Path]:
    for d in (cfg.paths.diffs, snapshot_dir(cfg) / "diffs"):
        found = sorted(d.glob(f"{ticker}_*.html")) if d.exists() else []
        if found:
            return found
    return []


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


if __name__ == "__main__":
    write_snapshot(load_config())
