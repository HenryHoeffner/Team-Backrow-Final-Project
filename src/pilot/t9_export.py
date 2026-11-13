"""T9: write everything worth looking at into one Excel workbook, outputs/lazy_prices.xlsx.

Sheets
  Firm-years    one row per scored 10-K: similarity, change, bin and the 12-month returns
  Firm summary  one row per firm: years scored, average excess return, years in Q1 / Q5
  Pooled by bin one row per bin: n, mean excess return, 95% CI, share beating the S&P 500
  Bin baskets   one row per bin and filing year (equal-weighted basket vs the S&P 500)
  Filings       one row per downloaded 10-K (accession number and file path)

Run after `plot`, which writes the pooled and basket tables this step copies.
"""
from __future__ import annotations

import logging

import pandas as pd

from pilot.config import Config, write_report

log = logging.getLogger("pilot.t9_export")

FIRM_YEAR_COLUMNS = [
    "ticker", "name", "sector", "fy", "prev_fy", "filing_date",
    "cosine_sim", "jaccard_sim", "cosine_risk_factors", "cosine_mdna",
    "change", "prior_median_change", "rel_change", "bin",
    "window_start", "window_end", "firm_return_pct", "spy_return_pct", "excess_return_pct", "partial",
]


def firm_year_table(cfg: Config, sim: pd.DataFrame, ret: pd.DataFrame) -> pd.DataFrame:
    """Similarity and return columns joined on (ticker, fy), one row per scored filing."""
    meta = pd.DataFrame([{"ticker": f.ticker, "name": f.name, "sector": f.sector} for f in cfg.firms])
    df = sim.merge(ret.drop(columns=["filing_date"]), on=["ticker", "fy"], how="left").merge(meta, on="ticker", how="left")
    df["bin"] = df["bin"].astype("Int64")
    return df[FIRM_YEAR_COLUMNS].sort_values(["ticker", "fy"]).reset_index(drop=True)


def firm_summary(firm_years: pd.DataFrame) -> pd.DataFrame:
    """Per firm, over full 12-month windows only (open windows would bias the average)."""
    full = firm_years[~firm_years["partial"].fillna(True).astype(bool)]
    g = full.groupby("ticker")
    out = pd.DataFrame({
        "years_with_full_window": g.size(),
        "avg_excess_return_pct": g["excess_return_pct"].mean(),
        "years_beating_sp500": g["excess_return_pct"].apply(lambda s: int((s > 0).sum())),
        "years_in_Q1": g["bin"].apply(lambda s: int((s == 1).sum())),
        "years_in_Q5": g["bin"].apply(lambda s: int((s == 5).sum())),
    }).reset_index()
    first = firm_years.drop_duplicates("ticker")[["ticker", "name", "sector"]]
    return first.merge(out, on="ticker", how="left")


def _format(ws, df: pd.DataFrame) -> None:
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for c, name in enumerate(df.columns, start=1):
        cell = ws.cell(row=1, column=c)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="3B4252")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        width = max([len(str(name))] + [len(str(v)) for v in df[name].head(200)])
        ws.column_dimensions[get_column_letter(c)].width = min(max(width + 2, 8), 44)
        is_float = pd.api.types.is_float_dtype(df[name])
        for r in range(2, len(df) + 2):
            if is_float:
                ws.cell(row=r, column=c).number_format = "0.0" if name.endswith("_pct") or name in ("mean", "sd", "ci_low", "ci_high", "basket", "spy") else "0.000"
    ws.row_dimensions[1].height = 32


def run_export(cfg: Config) -> pd.DataFrame:
    p = cfg.paths
    sim = pd.read_parquet(p.similarity)
    ret = pd.read_parquet(p.returns)
    fy = firm_year_table(cfg, sim, ret)

    sheets = {"Firm-years": fy, "Firm summary": firm_summary(fy)}
    for title, path in (("Pooled by bin", p.data / "pooled_by_bin.csv"), ("Bin baskets", p.data / "bin_baskets.csv")):
        if path.exists():
            sheets[title] = pd.read_csv(path)
        else:
            log.warning("%s missing; run the plot step first. Sheet '%s' skipped.", path.name, title)
    sheets["Filings"] = pd.read_csv(p.manifest)

    out = p.outputs / "lazy_prices.xlsx"
    p.outputs.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out, engine="openpyxl") as xw:
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name, index=False)
            _format(xw.sheets[name], df)

    write_report(cfg, "export", {"file": str(out.relative_to(p.root)),
                                 "sheets": {k: len(v) for k, v in sheets.items()}})
    print(f"\n[T9 check] wrote {out.relative_to(p.root)}: "
          + ", ".join(f"{k} ({len(v)} rows)" for k, v in sheets.items()))
    return fy
