"""T4: rank firms within each fiscal year into bins. Bin 1 = most changed, Bin 5 = least.

Two bases are computed and saved; `bin_basis` in config.yaml picks which one is `bin`:

- raw: rank on similarity to the prior-year 10-K. A firm whose 10-K is always wordier
  in its changes (INTC) lands in Q1 almost every year, so this mostly ranks firms.
- firm_relative: rank on this year's change (1 - similarity) divided by the firm's median
  change in its *earlier* scored years. "PFE changed 5.6x its usual amount" beats
  "INTC changed its usual amount". Only earlier years are used, so there is no lookahead.
"""
from __future__ import annotations

import logging
import math

import pandas as pd

from pilot.config import Config, write_report

log = logging.getLogger("pilot.t4_bins")
N_BINS = 5


def firm_relative_change(sim: pd.DataFrame, measure: str = "cosine_sim",
                         min_history: int = 2) -> pd.DataFrame:
    """Add change = 1 - measure, prior_median_change (the firm's median change over its
    earlier scored years) and rel_change = change / prior_median_change. rel_change is NaN
    until the firm has `min_history` earlier scored years."""
    s = sim.sort_values(["ticker", "fy"]).copy()
    s["change"] = 1.0 - s[measure]
    s["prior_median_change"] = s.groupby("ticker")["change"].transform(
        lambda c: c.shift(1).expanding(min_periods=min_history).median())
    base = s["prior_median_change"].where(s["prior_median_change"] > 0)
    s["rel_change"] = s["change"] / base
    return s


def assign_bins(sim: pd.DataFrame, measure: str = "cosine_sim",
                descending: bool = False) -> tuple[pd.DataFrame, list[dict]]:
    """Within each fy, rank on `measure` so the most-changed filing gets rank 1: ascending for
    a similarity, descending for a change score. Ties break alphabetically by ticker; then
    bin = ceil(5 * rank / n). Rows where `measure` is NaN get no rank or bin.
    Returns (table, ties)."""
    parts, ties = [], []
    scored = sim[sim[measure].notna()]
    for fy, g in scored.groupby("fy", sort=True):
        key = -g[measure] if descending else g[measure]
        g = g.assign(_k=key).sort_values(["_k", "ticker"], kind="mergesort").drop(columns="_k")
        n = len(g)
        g["rank"] = range(1, n + 1)
        g["bin"] = [math.ceil(N_BINS * r / n) for r in g["rank"]]
        for value, tg in g.groupby(measure):
            if len(tg) > 1:
                ties.append({"fy": int(fy), "value": float(value), "tickers": sorted(tg["ticker"])})
                log.warning("tie in FY%s on %s=%s: %s (broken alphabetically)", fy, measure, value,
                            sorted(tg["ticker"]))
        parts.append(g)
    unscored = sim[sim[measure].isna()]
    out = pd.concat(parts + [unscored]) if parts else sim.assign(rank=pd.NA, bin=pd.NA)
    out["rank"] = out["rank"].astype("Int64")
    out["bin"] = out["bin"].astype("Int64")
    return out.sort_values(["ticker", "fy"]).reset_index(drop=True), ties


def run_bins(cfg: Config) -> pd.DataFrame:
    from pilot.cli import CheckFailed

    p = cfg.paths
    sim = pd.read_parquet(p.similarity)
    sim = sim.drop(columns=[c for c in sim.columns if c in {
        "rank", "bin", "bin_raw", "bin_relative", "change", "prior_median_change", "rel_change"}])
    measure = f"{cfg.bin_measure}_sim"

    raw, ties_raw = assign_bins(sim, measure)
    rel = firm_relative_change(sim, measure, cfg.relative_min_history)
    rel, ties_rel = assign_bins(rel, "rel_change", descending=True)
    rel = rel.merge(raw[["ticker", "fy", "bin"]].rename(columns={"bin": "bin_raw"}), on=["ticker", "fy"])
    rel = rel.rename(columns={"bin": "bin_relative"}).drop(columns="rank")
    rel["bin"] = rel["bin_relative"] if cfg.bin_basis == "firm_relative" else rel["bin_raw"]
    binned = rel.sort_values(["ticker", "fy"]).reset_index(drop=True)
    binned.to_parquet(p.similarity, index=False)

    # ---- check
    with_bins = binned[binned["bin"].notna()]
    per_year = with_bins.groupby("fy")["bin"].apply(lambda b: sorted(int(x) for x in b)).to_dict()
    bad = {fy: b for fy, b in per_year.items() if b != list(range(1, N_BINS + 1))}
    no_bin_years = sorted(set(binned["fy"]) - set(per_year))
    ties = ties_rel if cfg.bin_basis == "firm_relative" else ties_raw
    q1_counts = with_bins[with_bins["bin"] == 1]["ticker"].value_counts().to_dict()
    q1_counts_raw = binned[binned["bin_raw"] == 1]["ticker"].value_counts().to_dict()
    write_report(cfg, "bins", {
        "measure": measure, "basis": cfg.bin_basis, "min_history": cfg.relative_min_history,
        "ties": ties, "bins_per_year": per_year, "years_without_full_bins": bad,
        "years_without_bins": no_bin_years, "q1_counts": q1_counts, "q1_counts_raw": q1_counts_raw,
    })
    label = ("change vs the firm's own earlier years" if cfg.bin_basis == "firm_relative"
             else measure)
    print(f"\n[T4 check] bins on {label}; Q1 = most changed")
    print(binned.pivot(index="ticker", columns="fy", values="bin").to_string())
    if cfg.bin_basis == "firm_relative":
        print("\nchange relative to the firm's earlier median (x times usual):")
        print(binned.pivot(index="ticker", columns="fy", values="rel_change").round(2).to_string())
        print(f"\nYears without bins (firms still building {cfg.relative_min_history} years of history): "
              f"{no_bin_years or 'none'}")
    print(f"[T4 check] every binned year has bins 1..5 exactly once: {not bad} {bad or ''}")
    print(f"[T4 check] Q1 count by firm: {q1_counts} (raw similarity bins: {q1_counts_raw})")
    print(f"[T4 check] ties: {ties or 'none'}")
    if bad and all(len(b) == N_BINS for b in bad.values()):
        raise CheckFailed(f"bins not 1..5 in years {sorted(bad)}")
    return binned
