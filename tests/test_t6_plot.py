import math

import pandas as pd
import pytest

from pilot.style import BIN_COLORS, bin_color, zero_is_sp500
from pilot.t6_plot import (basket_spread_test, bin_baskets, bin_summary, plot_combined, plot_firm, plot_heatmap,
                           plot_pooled, q5_minus_q1)


def test_bin_color_mapping():
    # Diverging: warm = most changed, gray = middle, blue = least changed.
    assert bin_color(1) == "#b8352a"
    assert bin_color(3) == "#9e9a91"
    assert bin_color(5) == "#1c5cab"
    assert len(BIN_COLORS) == 5 and len(set(BIN_COLORS.values())) == 5


def test_zero_tick_reads_sp500():
    f = zero_is_sp500(lambda v: f"{v:+.0f} pp")
    assert f(0) == "S&P 500"
    assert f(-50) == "−50 pp"


def _firm_rows(ticker="TEST"):
    return pd.DataFrame({
        "ticker": ticker,
        "filing_date": pd.to_datetime(["2021-02-01", "2022-02-01", "2023-02-01", "2024-02-01"]),
        "fy": [2020, 2021, 2022, 2023],
        "bin": pd.array([pd.NA, 1, 3, 5], dtype="Int64"),
        "firm_return_pct": [3.0, -10.0, 5.0, 20.0], "spy_return_pct": [1.0, -5.0, 15.0, 8.0],
        "excess_return_pct": [2.0, -5.0, -10.0, 12.0], "partial": [False, False, False, True],
        "window_end": pd.to_datetime(["2022-02-28", "2023-02-28", "2024-02-29", "2024-10-31"]),
    })


def test_plot_firm_writes_png(tmp_path):
    out = plot_firm({"ticker": "TEST", "name": "Test Co", "sector": "Industrials"}, _firm_rows(),
                    tmp_path / "f.png", "note")
    assert out.exists() and out.stat().st_size > 10_000


def _pool():
    # bin b gets returns b*10 + (-1, 0, +1)
    rows = [{"bin_a": b, "bin_b": 6 - b, "fy": 2020 + i, "ticker": f"T{b}",
             "excess_return_pct": b * 10.0 + d} for b in range(1, 6) for i, d in enumerate((-1, 0, 1))]
    return pd.DataFrame(rows)


def test_bin_summary_mean_ci_and_share():
    s = bin_summary(_pool(), "bin_a").set_index("bin")
    assert s.loc[3, "n"] == 3 and s.loc[3, "mean"] == pytest.approx(30.0)
    # sd = 1, t(0.975, 2) = 4.303 -> half width 4.303 / sqrt(3)
    assert s.loc[3, "ci_high"] - 30.0 == pytest.approx(4.302653 / math.sqrt(3), rel=1e-5)
    assert s.loc[3, "share_beat"] == 1.0


def test_q5_minus_q1_sign():
    assert q5_minus_q1(_pool(), "bin_a")["diff"] == pytest.approx(40.0)
    assert q5_minus_q1(_pool(), "bin_b")["diff"] == pytest.approx(-40.0)
    assert q5_minus_q1(_pool(), "bin_a")["p"] < 0.001


def _yearly_pool():
    """Three filing years, two firms per extreme bin each year. Yearly B5 - B1 = 10, 20, 30."""
    rows = []
    for i, gap in enumerate((10.0, 20.0, 30.0)):
        date = pd.Timestamp(f"{2020 + i}-02-15")
        rows += [{"ticker": t, "bin": b, "filing_date": date, "partial": False, "excess_return_pct": v}
                 for t, b, v in [("A", 1, -1.0), ("B", 1, 1.0), ("C", 5, gap - 5), ("D", 5, gap + 5),
                                 ("E", 3, 99.0)]]
    # A still-open window must be left out, even with a huge value.
    rows.append({"ticker": "C", "bin": 5, "filing_date": pd.Timestamp("2023-02-15"), "partial": True,
                 "excess_return_pct": 500.0})
    return pd.DataFrame(rows)


def test_basket_spread_test_uses_one_number_per_year():
    t = basket_spread_test(_yearly_pool(), "bin")
    assert [y["year"] for y in t["yearly"]] == [2020, 2021, 2022]
    assert [y["diff"] for y in t["yearly"]] == pytest.approx([10.0, 20.0, 30.0])
    assert t["n_years"] == 3 and t["diff"] == pytest.approx(20.0)
    # sd of (10, 20, 30) = 10, se = 10 / sqrt(3); t(0.975, 2) = 4.302653
    assert t["se"] == pytest.approx(10 / math.sqrt(3))
    assert t["ci_high"] - 20.0 == pytest.approx(4.302653 * 10 / math.sqrt(3), rel=1e-5)
    # t = 20 / (10 / sqrt 3) = 3.464 on 2 df -> two-sided p = 0.0742
    assert t["p"] == pytest.approx(0.0742, abs=1e-3)


def test_basket_spread_test_is_wider_than_pooled_welch():
    # Same average gap, but the honest test has 3 observations instead of 6 + 6.
    df = _yearly_pool()
    full = df[~df["partial"]]
    t, w = basket_spread_test(full, "bin"), q5_minus_q1(full, "bin")
    assert t["diff"] == pytest.approx(w["diff"])
    assert t["ci_high"] - t["ci_low"] > w["ci_high"] - w["ci_low"]


def test_basket_spread_test_needs_two_years():
    one = _yearly_pool().query("filing_date.dt.year == 2020")
    t = basket_spread_test(one, "bin")
    assert t["n_years"] == 1 and math.isnan(t["p"])


def test_plot_pooled_writes_png(tmp_path):
    summ, spread = plot_pooled(_pool(), tmp_path / "pooled.png", "bin_a", "note")
    assert (tmp_path / "pooled.png").stat().st_size > 10_000
    assert spread["diff"] == pytest.approx(40.0)


def test_bin_baskets_compound_against_sp500():
    df = pd.DataFrame({
        "ticker": ["A", "B", "A", "B"], "bin": [1, 1, 1, 1],
        "filing_date": pd.to_datetime(["2020-02-01", "2020-02-10", "2021-02-01", "2021-02-10"]),
        "firm_return_pct": [10.0, 30.0, 0.0, 0.0], "spy_return_pct": [10.0, 10.0, 10.0, 10.0],
        "partial": [False, False, False, True],
    })
    b = bin_baskets(df).set_index("year")
    assert b.loc[2020, "basket"] == pytest.approx(20.0) and b.loc[2020, "n"] == 2
    assert b.loc[2020, "relative"] == pytest.approx(1.2 / 1.1)
    assert b.loc[2021, "n"] == 1  # the partial window is left out
    assert b.loc[2021, "relative"] == pytest.approx((1.2 * 1.0) / (1.1 * 1.1))


def test_bin_baskets_keep_window_dates():
    # Each basket records its earliest hold start and latest hold end, used to label the x-axis.
    df = pd.DataFrame({
        "ticker": ["A", "B"], "bin": [1, 1],
        "filing_date": pd.to_datetime(["2020-01-15", "2020-02-10"]),
        "window_start": pd.to_datetime(["2020-01-31", "2020-02-28"]),
        "window_end": pd.to_datetime(["2021-01-29", "2021-02-26"]),
        "firm_return_pct": [10.0, 30.0], "spy_return_pct": [10.0, 10.0], "partial": [False, False],
    })
    b = bin_baskets(df).set_index("year")
    assert b.loc[2020, "window_start"] == pd.Timestamp("2020-01-31")
    assert b.loc[2020, "window_end"] == pd.Timestamp("2021-02-26")


def test_heatmap_and_combined_write_png(tmp_path):
    rows = pd.concat([_firm_rows("AAA"), _firm_rows("BBB")])
    firms = [{"ticker": "AAA", "name": "A", "sector": "X"}, {"ticker": "BBB", "name": "B", "sector": "Y"}]
    assert plot_heatmap(rows, firms, tmp_path / "h.png", "note").stat().st_size > 10_000
    assert plot_combined(bin_baskets(rows), tmp_path / "c.png", "note", 2).stat().st_size > 10_000
