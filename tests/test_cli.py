import subprocess
import sys
from pathlib import Path

from pilot.config import load_config

ROOT = Path(__file__).resolve().parents[1]


def test_config_loads():
    cfg = load_config(ROOT / "config.yaml", root=ROOT)
    assert cfg.tickers == ["INTC", "PFE", "JPM", "MCD", "CAT"]
    assert cfg.fiscal_years == list(range(2015, 2026))
    assert cfg.sections == ["risk_factors", "mdna"]
    assert cfg.bin_measure == "cosine"
    assert cfg.return_window_months == 12
    assert cfg.firm_by_cik("50863").ticker == "INTC"


def test_help_runs():
    out = subprocess.run([sys.executable, "-m", "pilot", "--help"], cwd=ROOT,
                         env={"PYTHONPATH": str(ROOT / "src")}, capture_output=True, text=True)
    assert out.returncode == 0
    for step in ("download", "clean", "score", "bins", "returns", "plot"):
        assert step in out.stdout
