"""T4: rank firms within each fiscal year into bins. Bin 1 = most changed, Bin 5 = least."""
from __future__ import annotations

import logging
import math

import pandas as pd

from pilot.config import Config, write_report

log = logging.getLogger("pilot.bins")
N_BINS = 5


def assign_bins(sim: pd.DataFrame, measure: str = "cosine_sim") -> tuple[pd.DataFrame, list[dict]]:
    """Within each fy, rank ascending on `measure` (lowest similarity = rank 1), ties broken
    alphabetically by ticker, then bin = ceil(5 * rank / n). Returns (table, ties)."""
    parts, ties = [], []
    for fy, g in sim.groupby("fy", sort=True):
        g = g.sort_values([measure, "ticker"], kind="mergesort").copy()
        n = len(g)
        g["rank"] = range(1, n + 1)
        g["bin"] = [math.ceil(N_BINS * r / n) for r in g["rank"]]
        for value, tg in g.groupby(measure):
            if len(tg) > 1:
                ties.append({"fy": int(fy), "value": float(value), "tickers": sorted(tg["ticker"])})
                log.warning("tie in FY%s on %s=%s: %s (broken alphabetically)", fy, measure, value,
                            sorted(tg["ticker"]))
        parts.append(g)
    out = pd.concat(parts) if parts else sim.assign(rank=[], bin=[])
    out["rank"] = out["rank"].astype(int)
    out["bin"] = out["bin"].astype(int)
    return out.sort_values(["ticker", "fy"]).reset_index(drop=True), ties


def run_bins(cfg: Config) -> pd.DataFrame:
    from pilot.cli import CheckFailed

    p = cfg.paths
    sim = pd.read_parquet(p.similarity)
    measure = f"{cfg.bin_measure}_sim"
    binned, ties = assign_bins(sim.drop(columns=["rank", "bin"], errors="ignore"), measure)
    binned.to_parquet(p.similarity, index=False)

    # ---- check
    per_year = binned.groupby("fy")["bin"].apply(sorted).to_dict()
    bad = {fy: b for fy, b in per_year.items() if b != list(range(1, N_BINS + 1))}
    write_report(cfg, "bins", {"measure": measure, "ties": ties, "bins_per_year": per_year,
                               "years_without_full_bins": bad})
    print(f"\n[T4 check] bins on {measure}; Q1 = most changed (lowest similarity)")
    print(binned.pivot(index="ticker", columns="fy", values="bin").to_string())
    print(f"[T4 check] every year has bins 1..5 exactly once: {not bad} {bad or ''}")
    print(f"[T4 check] ties: {ties or 'none'}")
    if bad and all(len(b) == N_BINS for b in bad.values()):
        raise CheckFailed(f"bins not 1..5 in years {sorted(bad)}")
    return binned
