from datetime import date

import pandas as pd
import pytest

from pilot.t5_returns import _index_from_returns, benchmark_total_return, compute_window, resolve_permnos


def _monthly(start="2021-01", periods=30, step=1.0):
    """Month-end trading-day prices: 100, 101, 102, ..."""
    months = pd.period_range(start, periods=periods, freq="M")
    # last business day of each month, as a trading-day stand-in
    dates = [m.to_timestamp(how="end").normalize() for m in months]
    dates = [d if d.weekday() < 5 else d - pd.offsets.BDay(1) for d in dates]
    return pd.Series([100 + step * i for i in range(periods)], index=pd.DatetimeIndex(dates))


def test_window_starts_at_filing_month_end_and_runs_12_months():
    px = _monthly()
    w = compute_window(date(2021, 2, 10), px, 12)
    assert w["window_start"] >= date(2021, 2, 10)
    assert (w["window_start"].year, w["window_start"].month) == (2021, 2)
    assert (w["window_end"].year, w["window_end"].month) == (2022, 2)
    assert w["return_pct"] == pytest.approx((113 / 101 - 1) * 100)
    assert w["partial"] is False


def test_year_rollover_from_december():
    px = _monthly()
    w = compute_window(date(2021, 12, 3), px, 12)
    assert (w["window_start"].year, w["window_start"].month) == (2021, 12)
    assert (w["window_end"].year, w["window_end"].month) == (2022, 12)


def test_filing_after_last_trading_day_rolls_to_next_month():
    px = _monthly()
    last_jan = px.index[0].date()  # last trading day of Jan 2021 (Fri 29th)
    w = compute_window(date(2021, 1, 31), px, 12)  # filed on the weekend after it
    assert last_jan < date(2021, 1, 31)
    assert w["window_start"] >= date(2021, 1, 31)
    assert (w["window_start"].year, w["window_start"].month) == (2021, 2)


def test_partial_window_uses_latest_month():
    px = _monthly(periods=18)  # Jan 2021 .. Jun 2022
    w = compute_window(date(2021, 11, 5), px, 12)
    assert w["partial"] is True
    assert (w["window_end"].year, w["window_end"].month) == (2022, 6)
    assert w["months"] == 7
    full = compute_window(date(2021, 6, 5), px, 12)  # ends Jun 2022 exactly: not partial
    assert full["partial"] is False


def test_index_from_returns_compounds_and_rejects_gaps():
    idx = pd.to_datetime(["2020-01-31", "2020-02-28", "2020-03-31"])
    out = _index_from_returns(pd.Series([None, 0.10, -0.50], index=idx), "X")
    assert out["adj_close"].tolist() == pytest.approx([100.0, 110.0, 55.0])
    gap = pd.Series([0.1, 0.1], index=pd.to_datetime(["2020-01-31", "2020-03-31"]))
    with pytest.raises(RuntimeError, match="missing months"):
        _index_from_returns(gap, "X")


def test_resolve_permnos_takes_latest_holder_of_reused_ticker():
    d = pd.to_datetime
    stocks = pd.DataFrame({
        "permno": [1, 2, 2], "ticker": ["COP", "COP", "COP"],
        "date": d(["2000-01-31", "2024-11-29", "2024-12-31"]), "mktcap": [5.0, 9.0, 9.0]})
    assert resolve_permnos(stocks, ["COP"]) == {"COP": 2}
    with pytest.raises(SystemExit):
        resolve_permnos(stocks, ["ZZZ"])


def _crsp_cfg(tmp_path):
    import shutil

    from pilot.config import PROJECT_ROOT, load_config

    shutil.copy(PROJECT_ROOT / "config.yaml", tmp_path / "config.yaml")
    cfg = load_config(root=tmp_path)
    cfg.paths.data.mkdir()
    return cfg


def test_prices_built_from_crsp_files(tmp_path):
    from pilot.t5_returns import CRSP_SOURCE, load_prices

    cfg = _crsp_cfg(tmp_path)
    dates = pd.date_range("2017-01-31", periods=6, freq="ME")
    stocks = pd.DataFrame([{"permno": 100 + i, "date": d, "ticker": t, "mktcap": 1.0, "ret_adj": 0.01}
                           for i, t in enumerate(cfg.tickers) for d in dates])
    stocks.to_parquet(cfg.paths.crsp_stocks)
    pd.DataFrame({"date": dates, "sprtrn": 0.02, "vwretd": 0.015, "vwretx": 0.01}).to_csv(cfg.paths.crsp_market, index=False)

    monthly, source = load_prices(cfg)
    assert source == CRSP_SOURCE
    spy = monthly[monthly["ticker"] == cfg.benchmark_ticker]["adj_close"].tolist()
    assert spy[-1] == pytest.approx(100 * 1.025 ** 5)
    assert cfg.paths.prices.exists() and cfg.paths.prices_source.read_text().startswith("CRSP")

    # Without the CRSP files, the committed cache is used and its origin is reported.
    cfg.paths.crsp_stocks.unlink()
    _, source = load_prices(cfg)
    assert source.startswith("cached data/prices_monthly.csv, CRSP")


def test_benchmark_adds_market_dividend_yield_to_sp500_price_return():
    m = pd.DataFrame({"date": pd.to_datetime(["2020-01-31", "2020-02-29"]), "sprtrn": [0.02, -0.01],
                      "vwretd": [0.031, 0.0], "vwretx": [0.030, -0.002]})
    assert benchmark_total_return(m).tolist() == pytest.approx([0.021, -0.008])
