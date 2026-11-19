"""Approximate S&P 500 membership at the start of each year from CRSP market cap.

Input : data/crsp_monthly_nyse_amex_nasdaq_2000plus.parquet (see data/README.md)
Output: data/sp500_proxy.csv  (one row per year x constituent)

Method
- For each start year Y, take the last month-end of Y-1 (the information available on
  the first trading day of Y).
- Market cap is `mktcap` (prc * shrout, $ thousands). Share classes of one company are
  summed by PERMCO (if the column exists) so GOOG/GOOGL, BRK.A/B etc. count once; the
  largest PERMNO represents the company.
- Rank by market cap and keep the top N (default 500).

This is a size-based proxy, NOT the real index: the actual S&P 500 uses a committee,
profitability and liquidity screens, and excludes some large firms (e.g. few non-US
domiciles). Expect roughly 80-90% overlap with the true list.

Usage: python data/sp500_proxy.py [--start 2001] [--end 2025] [--n 500]
"""
import argparse
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent
SRC = DATA / "crsp_monthly_nyse_amex_nasdaq_2000plus.parquet"
OUT = DATA / "sp500_proxy.csv"


def build(df: pd.DataFrame, start: int, end: int, n: int) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    date_col = next(c for c in ("date", "mthcaldt") if c in df.columns)
    df["date"] = pd.to_datetime(df[date_col])
    if "mktcap" not in df.columns:
        df["mktcap"] = df["prc"].abs() * df["shrout"]
    df = df.dropna(subset=["mktcap"])
    df = df[df["mktcap"] > 0]
    df["ym"] = df["date"].dt.to_period("M")

    id_col = "permco" if "permco" in df.columns else "permno"
    name_cols = [c for c in ("ticker", "comnam", "exchcd") if c in df.columns]

    frames = []
    for year in range(start, end + 1):
        # Last available month-end of the prior calendar year.
        prior = df[df["date"].dt.year == year - 1]
        if prior.empty:
            print(f"{year}: no data in {year - 1}, skipped")
            continue
        snap = prior[prior["ym"] == prior["ym"].max()]
        # Company-level cap = sum over share classes; representative = biggest permno.
        total = snap.groupby(id_col)["mktcap"].sum().rename("company_mktcap")
        rep = snap.sort_values("mktcap", ascending=False).drop_duplicates(id_col)
        rep = rep.set_index(id_col).join(total)
        top = rep.sort_values("company_mktcap", ascending=False).head(n)
        top = top.reset_index()
        top["start_year"] = year
        top["rank"] = range(1, len(top) + 1)
        top["asof_date"] = snap["date"].max()
        cols = ["start_year", "rank", "permno"] + ([id_col] if id_col != "permno" else []) \
            + name_cols + ["asof_date", "company_mktcap"]
        frames.append(top[cols])
        print(f"{year}: {len(top)} firms as of {snap['date'].max():%Y-%m-%d}, "
              f"cutoff cap ${top['company_mktcap'].iloc[-1] / 1e6:,.1f}B")
    return pd.concat(frames, ignore_index=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2001)
    ap.add_argument("--end", type=int, default=2025)
    ap.add_argument("--n", type=int, default=500)
    a = ap.parse_args()
    if not SRC.exists():
        raise SystemExit(f"Missing {SRC.name}. Put the CRSP parquet in data/ first (see data/README.md).")
    out = build(pd.read_parquet(SRC), a.start, a.end, a.n)
    out.to_csv(OUT, index=False)
    print(f"wrote {OUT} ({len(out)} rows)")


if __name__ == "__main__":
    main()
