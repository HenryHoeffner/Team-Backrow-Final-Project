import pandas as pd

from pilot.t6_plot import BIN_COLORS, bin_color, plot_firm


def test_bin_color_mapping():
    assert bin_color(1) == "#e41a1c"  # red = largest change
    assert bin_color(2) == "#ff9900"
    assert bin_color(3) == "#f2d600"
    assert bin_color(4) == "#a6e22e"
    assert bin_color(5) == "#1a9e1a"  # dark green = smallest change
    assert len(BIN_COLORS) == 5


def test_plot_firm_writes_png(tmp_path):
    df = pd.DataFrame({
        "filing_date": pd.to_datetime(["2022-02-01", "2023-02-01", "2024-02-01"]),
        "bin": [1, 3, 5], "firm_return_pct": [-10.0, 5.0, 20.0], "spy_return_pct": [-5.0, 15.0, 8.0],
        "partial": [False, False, True], "window_end": pd.to_datetime(["2023-02-28", "2024-02-29", "2024-10-31"]),
    })
    out = plot_firm("TEST", df, tmp_path / "t.png")
    assert out.exists() and out.stat().st_size > 10_000
