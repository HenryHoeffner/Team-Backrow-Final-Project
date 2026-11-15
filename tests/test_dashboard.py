"""Dashboard data (src/pilot/dashboard.py) and a headless run of app.py."""
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from pilot.config import PROJECT_ROOT, load_config
from pilot.dashboard import baskets, firm_years, pooled
from pilot.t6_plot import q5_minus_q1


def _write_pipeline_files(root: Path):
    """Two firms, two filing years each; the second AAA year is a still-open window."""
    shutil.copy(PROJECT_ROOT / "config.yaml", root / "config.yaml")
    (root / "data").mkdir()
    sim = pd.DataFrame({
        "ticker": ["INTC", "INTC", "PFE", "PFE"], "fy": [2018, 2019, 2018, 2019],
        "bin_relative": [1.0, 5.0, 5.0, None], "bin_raw": [1, 5, 5, 1], "cosine_sim": [0.9, 0.99, 0.98, 0.8],
        "change": [0.1, 0.01, 0.02, 0.2], "rel_change": [2.0, 0.5, 0.8, None]})
    ret = pd.DataFrame({
        "ticker": ["INTC", "INTC", "PFE", "PFE"], "fy": [2018, 2019, 2018, 2019],
        "filing_date": pd.to_datetime(["2019-02-01", "2020-02-01", "2019-02-20", "2020-02-20"]),
        "window_start": pd.to_datetime(["2019-02-28", "2020-02-28", "2019-02-28", "2020-02-28"]),
        "window_end": pd.to_datetime(["2020-02-28", "2020-10-30", "2020-02-28", "2020-10-30"]),
        "firm_return_pct": [5.0, 1.0, 20.0, 3.0], "spy_return_pct": [10.0, 2.0, 10.0, 2.0],
        "excess_return_pct": [-5.0, -1.0, 10.0, 1.0], "partial": [False, True, False, True]})
    sim.to_parquet(root / "data" / "similarity.parquet", index=False)
    ret.to_parquet(root / "data" / "returns.parquet", index=False)


def test_firm_years_keeps_binned_filings_with_firm_info(tmp_path):
    _write_pipeline_files(tmp_path)
    df = firm_years(load_config(root=tmp_path))
    assert len(df) == 3  # PFE FY2019 has no firm-relative bin
    assert df.loc[df["ticker"] == "PFE", "sector"].iloc[0] == "Health Care"
    assert df["filing_year"].tolist() == [2019, 2020, 2019]
    assert df["bin_relative"].dtype.kind == "i"


def test_pooled_uses_full_windows_only(tmp_path):
    _write_pipeline_files(tmp_path)
    df = firm_years(load_config(root=tmp_path))
    summary, spread = pooled(df, "bin_relative")
    # The open INTC FY2019 window (B5, -1) is left out: B5 is PFE alone (+10), B1 is INTC alone (-5).
    assert summary.set_index("bin").loc[5, "n"] == 1
    assert summary.set_index("bin").loc[5, "mean"] == pytest.approx(10.0)
    assert spread == q5_minus_q1(df[~df["partial"]], "bin_relative")


def test_baskets_start_level_with_the_market(tmp_path):
    _write_pipeline_files(tmp_path)
    b = baskets(firm_years(load_config(root=tmp_path)), "bin_relative")
    start = b[b["year"].isna()]
    assert sorted(start["bin"]) == [1, 2, 3, 4, 5] and (start["ahead_pct"] == 0).all()
    b1 = b[(b["bin"] == 1) & b["year"].notna()].iloc[0]
    assert b1["ahead_pct"] == pytest.approx((1.05 / 1.10 - 1) * 100)


@pytest.mark.skipif(not (PROJECT_ROOT / "data" / "returns.parquet").exists(),
                    reason="needs pipeline output: run make all")
def test_app_runs_and_matches_pipeline_report():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=60).run()
    assert not at.exception, at.exception
    # The headline B5 - B1 must be the number the plot step saved, so the site traces to outputs.
    saved = json.loads((PROJECT_ROOT / "data" / "reports" / "plot.json").read_text())
    diff = saved["pooled"]["bin"]["spread_q5_minus_q1"]["diff"]
    shown = next(m.value for m in at.metric if m.label == "B5 − B1")
    assert shown == f"{diff:+.1f} pp".replace("-", "−")
    # Switching the ranking and the firm must not break anything.
    at.radio[0].set_value("bin_raw").run()
    at.selectbox[0].set_value("PFE").run()
    assert not at.exception, at.exception
