"""Command line entry point: python -m pilot <step>."""
from __future__ import annotations

import argparse
import logging
import sys

from pilot.config import load_config


class CheckFailed(RuntimeError):
    """A task's check did not pass for a reason other than a recorded data gap."""


def _download(cfg, args):
    from pilot.download import run_download
    run_download(cfg)


def _clean(cfg, args):
    from pilot.clean import run_clean
    run_clean(cfg)


def _score(cfg, args):
    from pilot.score import run_score
    run_score(cfg)


def _bins(cfg, args):
    from pilot.bins import run_bins
    run_bins(cfg)


def _returns(cfg, args):
    from pilot.returns import run_returns
    run_returns(cfg, refresh=args.refresh)


def _plot(cfg, args):
    from pilot.plot import run_plot
    run_plot(cfg)


def _coverage(cfg, args):
    from pilot.coverage import run_coverage
    run_coverage(cfg)


def _diff(cfg, args):
    from pilot.diff import run_diff
    run_diff(cfg, ticker=args.ticker, fy=args.fy, lowest=args.lowest)


def _all(cfg, args):
    for step in (_download, _clean, _score, _bins, _returns, _plot, _coverage):
        step(cfg, args)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m pilot",
        description="Lazy Prices pilot: score year-over-year 10-K changes and plot next-year returns.",
    )
    p.add_argument("--config", help="path to config.yaml (default: project root)")
    p.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = p.add_subparsers(dest="cmd", required=True, metavar="STEP")
    sub.add_parser("download", help="T1: download 10-Ks and write data/filings_manifest.csv").set_defaults(fn=_download)
    sub.add_parser("clean", help="T2: extract and clean the 10-K document text").set_defaults(fn=_clean)
    sub.add_parser("score", help="T3: cosine and Jaccard similarity vs. prior-year 10-K").set_defaults(fn=_score)
    sub.add_parser("bins", help="T4: rank firms within each year into bins Q1..Q5").set_defaults(fn=_bins)
    r = sub.add_parser("returns", help="T5: 12-month firm and SPY returns after each filing")
    r.add_argument("--refresh", action="store_true", help="re-download prices even if cached")
    r.set_defaults(fn=_returns)
    sub.add_parser("plot", help="T6: one PNG per firm in outputs/figures/").set_defaults(fn=_plot)
    sub.add_parser("coverage", help="T7: write outputs/coverage.txt").set_defaults(fn=_coverage)
    d = sub.add_parser("diff", help="T8: HTML of sentences added/removed between two 10-Ks")
    d.add_argument("--ticker")
    d.add_argument("--fy", type=int)
    d.add_argument("--lowest", type=int, help="do the N lowest-similarity filings instead")
    d.set_defaults(fn=_diff)
    a = sub.add_parser("all", help="run T1..T7 in order")
    a.add_argument("--refresh", action="store_true", help="re-download prices even if cached")
    a.set_defaults(fn=_all)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    cfg = load_config(args.config)
    try:
        args.fn(cfg, args)
    except CheckFailed as e:
        logging.getLogger("pilot").error("CHECK FAILED: %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
