"""T7: one plain-text file listing what was found, what was scored and every gap."""
from __future__ import annotations

from datetime import date

from pilot.config import Config, read_report


def _lines(title: str, items) -> list[str]:
    items = list(items or [])
    return [f"{title}:{' none' if not items else ''}"] + [f"  - {i}" for i in items]


def run_coverage(cfg: Config) -> str:
    d = read_report(cfg, "download") or {}
    c = read_report(cfg, "clean") or {}
    s = read_report(cfg, "score") or {}
    b = read_report(cfg, "bins") or {}
    r = read_report(cfg, "returns") or {}
    pl = read_report(cfg, "plot") or {}
    n_firms, n_years = len(cfg.firms), len(cfg.fiscal_years)

    out = [
        "Lazy Prices pilot - coverage report",
        f"Generated {date.today().isoformat()} from data/reports/*.json",
        "",
        "FILINGS (T1)",
        f"10-K filings found: {d.get('rows', '?')} / {n_firms * n_years}"
        f" (fiscal years {cfg.fiscal_years[0]}-{cfg.fiscal_years[-1]})",
        f"Per firm: {d.get('per_firm')}",
        f"Fiscal years used: {d.get('effective_fiscal_years')}",
        f"Header company names match config: {not d.get('name_mismatches')}",
        *_lines("10-K/A amendments dropped",
                [f"{a['ticker']} {a['accession']} filed {a['filing_date']}" for a in d.get("amendments_dropped", [])]),
        *_lines("10-KT transition reports flagged (excluded)",
                [f"{a['ticker']} {a['accession']}" for a in d.get("transition_reports_flagged", [])]),
        *_lines("Download gaps", d.get("gaps")),
        "",
        "CLEAN TEXT (T2)",
        f"Clean files: {c.get('files', '?')} / {c.get('manifest_rows', '?')}",
        *_lines("Word-count outliers (>3x or <1/3 of firm median)",
                [f"{o['ticker']} FY{o['fy']}: {o['n_words']:,} words ({o['ratio_to_median']}x median)"
                 for o in c.get("size_outliers", [])]),
        *_lines("Clean gaps", c.get("gaps")),
        "",
        "SIMILARITY (T3) AND BINS (T4)",
        f"Scored filings: {s.get('rows', '?')} / {n_firms * (n_years - 1)}",
        f"Bin measure: {b.get('measure')}; Q1 = most changed, Q5 = least changed",
        *_lines("Years without exactly one of each bin 1-5", [f"FY{k}: {v}" for k, v in
                                                            (b.get("years_without_full_bins") or {}).items()]),
        *_lines("Ties (broken alphabetically by ticker)",
                [f"FY{t['fy']} {t['tickers']} at {t['value']:.6f}" for t in b.get("ties", [])]),
        *_lines("Lowest-similarity filings",
                [f"{x['ticker']} FY{x['fy']}: cosine {x['cosine_sim']:.4f}, jaccard {x['jaccard_sim']:.4f}"
                 for x in s.get("lowest", [])]),
        *_lines("Scoring gaps", s.get("gaps")),
        "",
        "RETURNS (T5)",
        f"Price source: {r.get('source')}",
        f"Latest complete price month: {r.get('latest_price_month')}",
        *_lines("Price coverage (monthly, last trading day)",
                [f"{t}: {v['first']} to {v['last']} ({v['months']} months)"
                 for t, v in (r.get("price_coverage") or {}).items()]),
        f"Return windows computed: {r.get('rows', '?')} / {s.get('rows', '?')}",
        *_lines("Partial windows (end month past latest price; hollow marker on graph)",
                [f"{x['ticker']} FY{x['fy']}: {x['window_start']} to {x['window_end']}"
                 for x in r.get("partial_windows", [])]),
        *_lines("Return gaps", r.get("gaps")),
        "",
        "FIGURES (T6)",
        *_lines("Figures", pl.get("figures")),
        f"Points per firm: {pl.get('points')}",
        "",
        "Reminder: 25 filings from 5 hand-picked firms illustrate the pipeline; they are not",
        "evidence for or against the Lazy Prices effect.",
    ]
    text = "\n".join(out) + "\n"
    cfg.paths.outputs.mkdir(parents=True, exist_ok=True)
    cfg.paths.coverage.write_text(text)
    print(text)
    return text
