"""Configuration and project paths."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
KNOWN_SECTIONS = ("risk_factors", "mdna")  # Item 1A, Item 7


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
    def sections(self) -> Path:
        return self.data / "sections"

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
    sections: list[str] = field(default_factory=lambda: ["risk_factors", "mdna"])
    bin_basis: str = "firm_relative"   # or "raw"
    relative_min_history: int = 2      # earlier scored years needed before a firm-relative score
    plot_return: str = "excess"        # or "raw"
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
    sections = [str(x) for x in raw.get("sections", ["risk_factors", "mdna"])]
    unknown = set(sections) - set(KNOWN_SECTIONS)
    if not sections or unknown:
        raise ValueError(f"sections must be a non-empty list from {KNOWN_SECTIONS}, got {sections!r}")
    basis = str(raw.get("bin_basis", "firm_relative"))
    if basis not in {"firm_relative", "raw"}:
        raise ValueError(f"bin_basis must be firm_relative or raw, got {basis!r}")
    plot_return = str(raw.get("plot_return", "excess"))
    if plot_return not in {"excess", "raw"}:
        raise ValueError(f"plot_return must be excess or raw, got {plot_return!r}")
    min_hist = int(raw.get("relative_min_history", 2))
    if min_hist < 1:
        raise ValueError("relative_min_history must be at least 1")
    return Config(
        bin_basis=basis,
        relative_min_history=min_hist,
        plot_return=plot_return,
        firms=[Firm(**{k: str(v) for k, v in f.items()}) for f in raw["firms"]],
        fiscal_years=sorted(int(y) for y in raw["fiscal_years"]),
        bin_measure=measure,
        return_window_months=int(raw.get("return_window_months", 12)),
        benchmark_ticker=str(raw.get("benchmark_ticker", "SPY")),
        sections=sections,
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
