"""T5: 12-month returns for each firm and SPY, starting at the month-end after the filing."""
from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from pilot.config import Config, write_report

log = logging.getLogger("pilot.t5_returns")

RETURN_COLUMNS = ["ticker", "fy", "filing_date", "window_start", "window_end",
                  "firm_return_pct", "spy_return_pct", "excess_return_pct", "partial"]
# excess_return_pct = firm minus SPY over the same window, in percentage points (market-adjusted;
# no beta adjustment).


class MissingPrice(KeyError):
    pass


# --------------------------------------------------------------------------- prices

CRSP_SOURCE = ("CRSP monthly (ret_adj, Shumway delisting rule); benchmark = CRSP sprtrn (S&P 500 price return) "
               "plus CRSP market dividend yield vwretd-vwretx (approximate total return)")


def resolve_permnos(stocks: pd.DataFrame, tickers: list[str]) -> dict[str, int]:
    """One PERMNO per ticker: the PERMNO that carried the ticker in the latest month it appears.
    Tickers get reused (COP, JPM, META each match two PERMNOs), so the most recent holder wins;
    the chosen PERMNO's whole history is used, so an old ticker (FB) is still followed."""
    out = {}
    for t in tickers:
        rows = stocks[stocks["ticker"] == t]
        if rows.empty:
            raise SystemExit(f"{t} not found in the CRSP stock file")
        last = rows[rows["date"] == rows["date"].max()]
        out[t] = int(last.sort_values("mktcap", ascending=False)["permno"].iloc[0])
    return out


def _index_from_returns(rets: pd.Series, name: str) -> pd.DataFrame:
    """Monthly returns (index = month-end dates) -> long table of a total-return index (first = 100).
    Raises if a month is missing in the middle, since compounding would silently skip it."""
    rets = rets.sort_index()
    months = rets.index.to_period("M")
    full = pd.period_range(months.min(), months.max(), freq="M")
    if len(full) != len(months):
        missing = [str(m) for m in full.difference(months)]
        raise RuntimeError(f"{name}: missing months {missing[:5]}")
    rets = rets.fillna(0.0)
    rets.iloc[0] = 0.0  # the index starts at 100 in the first month
    level = 100.0 * (1.0 + rets).cumprod()
    return pd.DataFrame({"date": level.index, "ticker": name, "adj_close": level.values})


def benchmark_total_return(market: pd.DataFrame) -> pd.Series:
    """Approximate S&P 500 total return: its price return (sprtrn) plus the dividend return of the
    CRSP value-weighted market (vwretd - vwretx). CRSP has no S&P 500 total return, and the market's
    dividend yield is close to the index's, so the error is a few basis points a year."""
    m = market.set_index("date").sort_index()
    return m["sprtrn"] + (m["vwretd"] - m["vwretx"])


def build_prices_from_crsp(cfg: Config) -> pd.DataFrame:
    """Month-end total-return index for every firm and the benchmark, from the CRSP files.
    Firms use ret_adj (dividends and delisting returns); the benchmark is benchmark_total_return()."""
    p = cfg.paths
    for f in (p.crsp_stocks, p.crsp_market):
        if not f.exists():
            raise FileNotFoundError(f)
    stocks = pd.read_parquet(p.crsp_stocks, columns=["permno", "date", "ticker", "mktcap", "ret_adj"])
    stocks["date"] = pd.to_datetime(stocks["date"])
    permnos = resolve_permnos(stocks, cfg.tickers)
    log.info("CRSP PERMNOs: %s", permnos)
    out = []
    for t, pn in permnos.items():
        s = stocks[stocks["permno"] == pn].set_index("date")["ret_adj"]
        out.append(_index_from_returns(s, t))
        if s.index.max() < stocks["date"].max():
            log.warning("%s (PERMNO %s) has CRSP data only through %s; later windows will be gaps. "
                        "The stock file keeps only SHRCD 10/11, so a firm that became a REIT drops out.",
                        t, pn, s.index.max().date())
    out.append(_index_from_returns(benchmark_total_return(pd.read_csv(p.crsp_market, parse_dates=["date"])),
                                   cfg.benchmark_ticker))
    return pd.concat(out, ignore_index=True)


def load_prices(cfg: Config) -> tuple[pd.DataFrame, str]:
    """Build prices from the CRSP files when they are present (and refresh the committed cache);
    otherwise use the cached data/prices_monthly.csv so `make from-scores` works on a clone."""
    p = cfg.paths
    tickers = cfg.tickers + [cfg.benchmark_ticker]
    if p.crsp_stocks.exists() and p.crsp_market.exists():
        monthly = build_prices_from_crsp(cfg)
        monthly.to_csv(p.prices, index=False)
        p.prices_source.write_text(CRSP_SOURCE + "\n")
        return monthly, CRSP_SOURCE
    if p.prices.exists():
        cached = pd.read_csv(p.prices, parse_dates=["date"])
        origin = p.prices_source.read_text().strip() if p.prices_source.exists() else "origin not recorded"
        if not origin.startswith("CRSP"):
            raise SystemExit(f"cached {p.prices.name} is not from CRSP ({origin}); put the CRSP files in data/")
        if not set(tickers) <= set(cached["ticker"]):
            raise SystemExit("cached prices are missing tickers; put the CRSP files in data/ to rebuild")
        return cached, f"cached {p.prices.relative_to(p.root)}, {origin}"
    raise SystemExit(f"no CRSP files ({p.crsp_stocks.name}, {p.crsp_market.name}) and no cached prices in data/")


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


def run_returns(cfg: Config) -> pd.DataFrame:
    from pilot.cli import CheckFailed

    p = cfg.paths
    sim = pd.read_parquet(p.similarity)
    sim["filing_date"] = pd.to_datetime(sim["filing_date"]).dt.date
    monthly, source = load_prices(cfg)
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
                     "excess_return_pct": fw["return_pct"] - bw["return_pct"],
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
                     spy_return_pct=ret.spy_return_pct.round(1),
                     excess_return_pct=ret.excess_return_pct.round(1)).to_string(index=False))
    print(f"[T5 check] window start on/after filing date in every row: {start_ok}")
    print(f"[T5 check] partial flag true only where end month is past latest price: {partial_ok}")
    if gaps:
        print(f"[T5 check] gaps: {gaps}")
    if not (start_ok and partial_ok):
        raise CheckFailed("return window check failed")
    return ret
