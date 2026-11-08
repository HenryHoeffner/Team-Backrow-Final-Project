import math

import pandas as pd
import pytest

from pilot.t6_plot import BIN_COLORS, bin_color, bin_summary, plot_firm, plot_pooled, q5_minus_q1


def test_bin_color_mapping():
    assert bin_color(1) == "#e41a1c"  # red = largest change
    assert bin_color(2) == "#ff9900"
    assert bin_color(3) == "#f2d600"
    assert bin_color(4) == "#a6e22e"
    assert bin_color(5) == "#1a9e1a"  # dark green = smallest change
    assert len(BIN_COLORS) == 5


def _firm():
    return pd.DataFrame({
        "filing_date": pd.to_datetime(["2021-02-01", "2022-02-01", "2023-02-01", "2024-02-01"]),
        "bin": pd.array([pd.NA, 1, 3, 5], dtype="Int64"),
        "firm_return_pct": [3.0, -10.0, 5.0, 20.0], "spy_return_pct": [1.0, -5.0, 15.0, 8.0],
        "excess_return_pct": [2.0, -5.0, -10.0, 12.0], "partial": [False, False, False, True],
        "window_end": pd.to_datetime(["2022-02-28", "2023-02-28", "2024-02-29", "2024-10-31"]),
    })


@pytest.mark.parametrize("mode", ["excess", "raw"])
def test_plot_firm_writes_png(tmp_path, mode):
    out = plot_firm("TEST", _firm(), tmp_path / f"{mode}.png", "footnote", mode=mode)
    assert out.exists() and out.stat().st_size > 10_000


def _pool():
    # bin b gets returns b*10 + (-1, 0, +1)
    rows = [{"bin_a": b, "bin_b": 6 - b, "fy": 2020 + i, "ticker": "X",
             "excess_return_pct": b * 10.0 + d} for b in range(1, 6) for i, d in enumerate((-1, 0, 1))]
    return pd.DataFrame(rows)


def test_bin_summary_mean_and_ci():
    s = bin_summary(_pool(), "bin_a").set_index("bin")
    assert s.loc[3, "n"] == 3 and s.loc[3, "mean"] == pytest.approx(30.0)
    # sd = 1, t(0.975, 2) = 4.303 -> half width 4.303 / sqrt(3)
    assert s.loc[3, "ci_high"] - 30.0 == pytest.approx(4.302653 / math.sqrt(3), rel=1e-5)


def test_q5_minus_q1_sign():
    assert q5_minus_q1(_pool(), "bin_a")["diff"] == pytest.approx(40.0)
    assert q5_minus_q1(_pool(), "bin_b")["diff"] == pytest.approx(-40.0)
    assert q5_minus_q1(_pool(), "bin_a")["p"] < 0.001


def test_plot_pooled_writes_png(tmp_path):
    res = plot_pooled(_pool(), tmp_path / "pooled.png", [("bin_a", "A"), ("bin_b", "B")], "note")
    assert (tmp_path / "pooled.png").stat().st_size > 10_000
    assert set(res) == {"bin_a", "bin_b"}
