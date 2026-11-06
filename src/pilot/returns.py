"""T5: 12-month returns for each firm and SPY, starting at the month-end after the filing."""
from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from pilot.config import Config, write_report

log = logging.getLogger("pilot.returns")

RETURN_COLUMNS = ["ticker", "fy", "filing_date", "window_start", "window_end",
                  "firm_return_pct", "spy_return_pct", "partial"]


class MissingPrice(KeyError):
    pass


# --------------------------------------------------------------------------- prices


def month_end_prices(daily: pd.DataFrame) -> pd.DataFrame:
    """Daily adjusted closes (index = dates, columns = tickers) -> long table of the last
    trading day's close in each month: date, ticker, adj_close."""
    daily = daily.sort_index()
    out = []
    for t in daily.columns:
        s = daily[t].dropna()
        last = s.groupby(s.index.to_period("M")).tail(1)
        out.append(pd.DataFrame({"date": last.index, "ticker": t, "adj_close": last.values}))
    return pd.concat(out, ignore_index=True)


def drop_incomplete_month(monthly: pd.DataFrame, today: date) -> pd.DataFrame:
    """The current calendar month has not closed yet, so its 'month-end' is not one."""
    cur = pd.Period(today, "M")
    return monthly[pd.to_datetime(monthly["date"]).dt.to_period("M") < cur].reset_index(drop=True)


def download_prices(tickers: list[str], start: date, end: date) -> pd.DataFrame:
    import yfinance as yf

    df = yf.download(tickers, start=start.isoformat(), end=end.isoformat(), interval="1d",
                     auto_adjust=True, progress=False, threads=False, group_by="column")
    if df is None or df.empty:
        raise RuntimeError("yfinance returned no data")
    close = df["Close"] if isinstance(df.columns, pd.MultiIndex) else df[["Close"]].rename(
        columns={"Close": tickers[0]})
    missing = [t for t in tickers if t not in close.columns or close[t].dropna().empty]
    if missing:
        raise RuntimeError(f"yfinance returned no prices for {missing}")
    close.index = pd.to_datetime(close.index).tz_localize(None)
    return month_end_prices(close[tickers])


def load_prices(cfg: Config, start: date, refresh: bool = False) -> tuple[pd.DataFrame, str]:
    p = cfg.paths
    tickers = cfg.tickers + [cfg.benchmark_ticker]
    if p.prices.exists() and not refresh:
        source = f"cached {p.prices.relative_to(p.root)}"
        monthly = pd.read_csv(p.prices, parse_dates=["date"])
    else:
        try:
            monthly = download_prices(tickers, start, date.today())
            monthly = drop_incomplete_month(monthly, date.today())
            monthly.to_csv(p.prices, index=False)
            source = f"yfinance (downloaded {date.today().isoformat()})"
        except Exception as e:  # network, rate limit, API change
            ext = p.external / "prices_monthly.csv"
            if not ext.exists():
                raise SystemExit(f"price download failed ({e}) and no fallback CSV at {ext} "
                                 "(columns: date, ticker, adj_close)") from e
            log.warning("yfinance failed (%s); using %s", e, ext)
            monthly = pd.read_csv(ext, parse_dates=["date"])
            source = f"fallback CSV {ext.relative_to(p.root)} (yfinance failed: {e})"
    return monthly, source


# --------------------------------------------------------------------------- window


def compute_window(filing_date: date, prices: pd.Series, months: int = 12) -> dict:
    """Return over [m0, m0 + months], where m0 is the last trading day of the filing month.

    `prices` is indexed by month-end trading dates. If the filing landed after that month's
    last trading day, the window starts at the next month-end so it never precedes the filing.
    If m0 + months is past the latest price, the latest month is used and partial=True.
    """
    prices = prices.dropna().sort_index()
    prices.index = pd.to_datetime(prices.index)
    last = prices.groupby(prices.index.to_period("M")).tail(1)  # one price per month
    by_month = pd.Series(last.values, index=last.index.to_period("M"))
    dates = pd.Series(last.index, index=last.index.to_period("M"))

    m0 = pd.Period(filing_date, "M")
    if m0 in dates.index and dates[m0].date() < filing_date:
        m0 += 1
    if m0 not in by_month.index:
        raise MissingPrice(f"no month-end price for {m0}")
    end = m0 + months
    latest = by_month.index.max()
    partial = end > latest
    if partial:
        end = latest
    if end not in by_month.index:
        raise MissingPrice(f"no month-end price for {end}")
    return {
        "window_start": dates[m0].date(), "window_end": dates[end].date(),
        "return_pct": (by_month[end] / by_month[m0] - 1.0) * 100.0, "partial": bool(partial),
        "months": (end - m0).n,
    }


# --------------------------------------------------------------------------- main step


def run_returns(cfg: Config, refresh: bool = False) -> pd.DataFrame:
    from pilot.cli import CheckFailed

    p = cfg.paths
    sim = pd.read_parquet(p.similarity)
    sim["filing_date"] = pd.to_datetime(sim["filing_date"]).dt.date
    start = (pd.Timestamp(min(sim["filing_date"])) - pd.offsets.MonthBegin(2)).date()
    monthly, source = load_prices(cfg, start, refresh=refresh)
    wide = monthly.pivot(index="date", columns="ticker", values="adj_close").sort_index()
    bench = cfg.benchmark_ticker

    rows, gaps = [], []
    for r in sim.sort_values(["ticker", "fy"]).itertuples():
        try:
            fw = compute_window(r.filing_date, wide[r.ticker], cfg.return_window_months)
            bw = compute_window(r.filing_date, wide[bench], cfg.return_window_months)
        except (MissingPrice, KeyError) as e:
            gaps.append(f"{r.ticker} FY{r.fy}: {e}")
            continue
        if (fw["window_start"], fw["window_end"]) != (bw["window_start"], bw["window_end"]):
            gaps.append(f"{r.ticker} FY{r.fy}: firm and {bench} windows differ {fw} vs {bw}")
        rows.append({"ticker": r.ticker, "fy": r.fy, "filing_date": r.filing_date,
                     "window_start": fw["window_start"], "window_end": fw["window_end"],
                     "firm_return_pct": fw["return_pct"], "spy_return_pct": bw["return_pct"],
                     "partial": fw["partial"]})
    ret = pd.DataFrame(rows, columns=RETURN_COLUMNS)
    for c in ("filing_date", "window_start", "window_end"):
        ret[c] = pd.to_datetime(ret[c])
    ret.to_parquet(p.returns, index=False)

    # ---- check
    latest = pd.Timestamp(wide.index.max())
    start_ok = bool((ret["window_start"] >= ret["filing_date"]).all())
    should_be_partial = [
        (pd.Period(fd, "M") + cfg.return_window_months) > latest.to_period("M")
        for fd in ret["filing_date"]
    ]
    partial_ok = ret["partial"].tolist() == should_be_partial
    coverage = {t: {"first": str(wide[t].first_valid_index().date()),
                    "last": str(wide[t].last_valid_index().date()),
                    "months": int(wide[t].notna().sum())} for t in wide.columns}
    write_report(cfg, "returns", {
        "rows": len(ret), "source": source, "latest_price_month": latest.strftime("%b %Y"),
        "price_coverage": coverage, "gaps": gaps, "start_after_filing": start_ok,
        "partial_flag_correct": partial_ok,
        "partial_windows": ret[ret["partial"]][["ticker", "fy", "window_start", "window_end"]]
        .astype(str).to_dict("records"),
    })
    print(f"\n[T5 check] prices from {source}; latest month-end {latest.date()}")
    print(ret.assign(firm_return_pct=ret.firm_return_pct.round(1),
                     spy_return_pct=ret.spy_return_pct.round(1)).to_string(index=False))
    print(f"[T5 check] window start on/after filing date in every row: {start_ok}")
    print(f"[T5 check] partial flag true only where end month is past latest price: {partial_ok}")
    if gaps:
        print(f"[T5 check] gaps: {gaps}")
    if not (start_ok and partial_ok):
        raise CheckFailed("return window check failed")
    return ret
