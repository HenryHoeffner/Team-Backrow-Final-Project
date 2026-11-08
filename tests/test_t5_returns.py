from datetime import date

import pandas as pd
import pytest

from pilot.t5_returns import compute_window, drop_incomplete_month, month_end_prices


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


def test_month_end_prices_and_incomplete_month():
    idx = pd.to_datetime(["2026-09-29", "2026-09-30", "2026-10-30", "2026-11-04"])
    daily = pd.DataFrame({"X": [1.0, 2.0, 3.0, 4.0]}, index=idx)
    m = month_end_prices(daily)
    assert m["adj_close"].tolist() == [2.0, 3.0, 4.0]
    kept = drop_incomplete_month(m, date(2026, 11, 6))
    assert kept["adj_close"].tolist() == [2.0, 3.0]
