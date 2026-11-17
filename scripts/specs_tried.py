"""Rerun the pooled B5 - B1 comparison under each specification listed in specs_tried.md.

Reads data/similarity.parquet and data/returns.parquet (written by `make all`) and reuses the
pipeline's own functions (t4 binning, t6 statistics), so each row differs from the headline
only in the one choice it names. Prints a Markdown table.

    PYTHONPATH=src .venv/bin/python scripts/specs_tried.py
"""
from __future__ import annotations

import pandas as pd

from pilot.t4_bins import assign_bins, firm_relative_change
from pilot.t6_plot import q5_minus_q1

SIM = pd.read_parquet("data/similarity.parquet")
RET = pd.read_parquet("data/returns.parquet")
BASE = SIM.drop(columns=[c for c in SIM.columns if c in {
    "rank", "bin", "bin_raw", "bin_relative", "change", "prior_median_change", "rel_change"}])


def spec(measure: str, basis: str, min_history: int = 2, min_fy: int = 0) -> pd.DataFrame:
    """One bin per firm-year for this measure/basis, joined to returns (full windows only)."""
    s = BASE.copy()
    if basis == "raw":
        s, _ = assign_bins(s, measure)
    else:
        s = firm_relative_change(s, measure, min_history)
        s, _ = assign_bins(s, "rel_change", descending=True)
    df = RET.merge(s[["ticker", "fy", "bin"]], on=["ticker", "fy"], how="inner", validate="one_to_one")
    return df[~df["partial"] & df["bin"].notna() & (df["fy"] >= min_fy)]


SPECS = [
    ("Headline: cosine, Item 1A + 7 combined, firm-relative, min history 2", "cosine_sim", "firm_relative", 2),
    ("Raw similarity bins (`bin_basis: raw`), same years as headline", "cosine_sim", "raw", 2, 2018),
    ("Raw similarity bins (`bin_basis: raw`), all scored years", "cosine_sim", "raw", 2),
    ("Firm-relative, `relative_min_history: 1`", "cosine_sim", "firm_relative", 1),
    ("Firm-relative, `relative_min_history: 3`", "cosine_sim", "firm_relative", 3),
    ("Jaccard instead of cosine, firm-relative", "jaccard_sim", "firm_relative", 2),
    ("Jaccard instead of cosine, raw", "jaccard_sim", "raw", 2),
    ("Item 1A (Risk Factors) only, firm-relative", "cosine_risk_factors", "firm_relative", 2),
    ("Item 7 (MD&A) only, firm-relative", "cosine_mdna", "firm_relative", 2),
]

print("| Specification | Years | B1 n | B5 n | B1 mean | B5 mean | B5 − B1 (pp) | 95% CI | Welch p |")
print("|---|---|---|---|---|---|---|---|---|")
for label, *args in SPECS:
    df = spec(*args)
    r = q5_minus_q1(df, "bin")
    m = df.groupby("bin")["excess_return_pct"].mean()
    yrs = f"FY{df['fy'].min()}–FY{df['fy'].max()}"
    print(f"| {label} | {yrs} | {r['n1']} | {r['n5']} | {m[1]:+.2f} | {m[5]:+.2f} | {r['diff']:+.2f} | "
          f"{r['ci_low']:+.1f} to {r['ci_high']:+.1f} | {r['p']:.2f} |")
