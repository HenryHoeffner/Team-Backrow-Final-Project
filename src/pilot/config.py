"""Configuration and project paths."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Firm:
    ticker: str
    cik: str
    name: str
    sector: str


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def raw(self) -> Path:
        return self.data / "raw"

    @property
    def clean(self) -> Path:
        return self.data / "clean"

    @property
    def external(self) -> Path:
        return self.data / "external"

    @property
    def reports(self) -> Path:
        return self.data / "reports"

    @property
    def manifest(self) -> Path:
        return self.data / "filings_manifest.csv"

    @property
    def similarity(self) -> Path:
        return self.data / "similarity.parquet"

    @property
    def prices(self) -> Path:
        return self.data / "prices_monthly.csv"

    @property
    def returns(self) -> Path:
        return self.data / "returns.parquet"

    @property
    def outputs(self) -> Path:
        return self.root / "outputs"

    @property
    def figures(self) -> Path:
        return self.outputs / "figures"

    @property
    def diffs(self) -> Path:
        return self.outputs / "diffs"

    @property
    def coverage(self) -> Path:
        return self.outputs / "coverage.txt"


@dataclass(frozen=True)
class Config:
    firms: list[Firm]
    fiscal_years: list[int]
    bin_measure: str
    return_window_months: int
    benchmark_ticker: str
    paths: Paths = field(default_factory=lambda: Paths(PROJECT_ROOT))

    @property
    def tickers(self) -> list[str]:
        return [f.ticker for f in self.firms]

    def firm_by_cik(self, cik: str) -> Firm | None:
        key = str(cik).lstrip("0")
        for f in self.firms:
            if f.cik.lstrip("0") == key:
                return f
        return None


def load_config(path: Path | None = None, root: Path | None = None) -> Config:
    root = Path(root or os.environ.get("PILOT_ROOT", PROJECT_ROOT))
    path = Path(path or root / "config.yaml")
    raw = yaml.safe_load(path.read_text())
    measure = raw.get("bin_measure", "cosine")
    if measure not in {"cosine", "jaccard"}:
        raise ValueError(f"bin_measure must be cosine or jaccard, got {measure!r}")
    return Config(
        firms=[Firm(**{k: str(v) for k, v in f.items()}) for f in raw["firms"]],
        fiscal_years=sorted(int(y) for y in raw["fiscal_years"]),
        bin_measure=measure,
        return_window_months=int(raw.get("return_window_months", 12)),
        benchmark_ticker=str(raw.get("benchmark_ticker", "SPY")),
        paths=Paths(root),
    )


def write_report(cfg: Config, stage: str, report: dict) -> Path:
    """Save a stage's check results and data gaps for the coverage report."""
    cfg.paths.reports.mkdir(parents=True, exist_ok=True)
    out = cfg.paths.reports / f"{stage}.json"
    out.write_text(json.dumps(report, indent=2, default=str, sort_keys=True))
    return out


def read_report(cfg: Config, stage: str) -> dict | None:
    p = cfg.paths.reports / f"{stage}.json"
    return json.loads(p.read_text()) if p.exists() else None
