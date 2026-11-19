"""Licensed CRSP data must never be committed (src/pilot/licensing.py, README_DATA.md)."""
import subprocess

import pandas as pd
import pytest

from pilot.config import PROJECT_ROOT
from pilot.licensing import find_problems, is_data_file, problems_in


def test_no_licensed_data_in_tracked_files():
    found = find_problems(PROJECT_ROOT)
    if found is None:
        pytest.skip("git not available")
    assert found == [], "CRSP data is tracked by git:\n" + "\n".join(found)


def test_crsp_files_and_series_built_from_them_are_git_ignored():
    names = ["data/crsp_monthly_nyse_amex_nasdaq_2000plus.parquet", "data/crsp_monthly_market.csv",
             "data/prices_monthly.csv", "data/prices_monthly.source.txt", "data/returns.parquet"]
    try:
        out = subprocess.run(["git", "check-ignore", *names], cwd=PROJECT_ROOT,
                             capture_output=True, text=True)
    except OSError:
        pytest.skip("git not available")
    assert sorted(out.stdout.split()) == sorted(names)


def test_flags_crsp_extracts_series_and_named_files(tmp_path):
    pd.DataFrame({"permno": [1], "date": ["2020-01-31"], "ret_adj": [0.1]}).to_parquet(tmp_path / "panel.parquet")
    pd.DataFrame({"date": ["2020-01-31"], "vwretd": [0.01]}).to_csv(tmp_path / "mkt.csv", index=False)
    pd.DataFrame({"date": ["2020-01-31"], "ticker": ["INTC"], "adj_close": [100.0]}).to_csv(
        tmp_path / "index.csv", index=False)
    (tmp_path / "wrds_pull.csv").write_text("a,b\n")

    assert "CRSP columns ['permno', 'ret_adj']" in problems_in(tmp_path / "panel.parquet", "x/panel.parquet")[0]
    assert "vwretd" in problems_in(tmp_path / "mkt.csv", "data/mkt.csv")[0]
    assert "adj_close" in problems_in(tmp_path / "index.csv", "app_data/index.csv")[0]
    assert "file name" in problems_in(tmp_path / "wrds_pull.csv", "data/wrds_pull.csv")[0]
    assert "git-ignored" in problems_in(tmp_path / "missing.csv", "data/prices_monthly.csv")[0]


def test_allows_results_code_and_docs(tmp_path):
    # The dashboard's firm-year table and coverage report are results, even when computed from CRSP.
    cols = ["ticker", "fy", "filing_date", "bin_relative", "firm_return_pct", "spy_return_pct", "excess_return_pct"]
    pd.DataFrame([["INTC", 2019, "2020-01-24", 3, 5.0, 10.0, -5.0]], columns=cols).to_csv(
        tmp_path / "firm_years.csv", index=False)
    (tmp_path / "coverage.txt").write_text("Price source: CRSP monthly\n")
    for name in ("firm_years.csv", "coverage.txt"):
        assert problems_in(tmp_path / name, f"app_data/{name}") == [], name
    assert not is_data_file("src/pilot/t5_returns.py") and not is_data_file("README_DATA.md")
    assert is_data_file("data/similarity.parquet") and is_data_file("notes/extract.parquet")
