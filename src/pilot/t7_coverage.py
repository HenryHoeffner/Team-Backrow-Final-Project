"""T7: one plain-text file listing what was found, what was scored and every gap."""
from __future__ import annotations

from datetime import date

from pilot.config import Config, read_report
from pilot.t2_sections import SECTION_NAMES


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
        f"Sections scored: {' + '.join(SECTION_NAMES[x] for x in cfg.sections)}",
        *_lines("Sections taken from an EX-13 annual-report exhibit (incorporated by reference)",
                [f"{x['ticker']} FY{x['fy']}: {SECTION_NAMES[x['section']]}" for x in c.get("sections_from_exhibit", [])]),
        *_lines("Section word-count outliers (>3x or <1/3 of firm median)",
                [f"{o['ticker']} FY{o['fy']} {SECTION_NAMES[o['section']]}: {o['n_words']:,} words "
                 f"({o['ratio_to_median']}x median)" for o in c.get("section_outliers", [])]),
        *_lines("Clean and section gaps", c.get("gaps")),
        "",
        "SIMILARITY (T3) AND BINS (T4)",
        f"Scored filings: {s.get('rows', '?')} / {n_firms * (n_years - 1)}",
        f"Bin measure: {b.get('measure')}; basis: {b.get('basis')}"
        + (f" (change / firm's median change in earlier years, needs {b.get('min_history')} earlier years)"
           if b.get("basis") == "firm_relative" else "")
        + "; Q1 = most changed, Q5 = least changed",
        *_lines("Years without bins (firm history still building)", [f"FY{y}" for y in b.get("years_without_bins", [])]),
        f"Q1 count by firm: {b.get('q1_counts')} (raw-similarity bins: {b.get('q1_counts_raw')})",
        *_lines("Years whose bins do not match ceil(5 * rank / n)", [f"FY{k}: {v}" for k, v in
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
        "Per-firm y axis: return minus the S&P 500 over the same window (pp)",
        "",
        "POOLED: NEXT-YEAR RETURN MINUS S&P 500 BY BIN (T6)",
        f"Firm-years: {pl.get('pooled_n')} (FY{min(pl.get('pooled_years') or [0])}-FY{max(pl.get('pooled_years') or [0])}"
        "; full 12-month windows only)",
        *[line for col, res in (pl.get("pooled") or {}).items() for line in [
            f"{'Bins used (firm-relative)' if col == 'bin' else 'Raw-similarity bins, for comparison'}: "
            + ", ".join(f"Q{x['bin']} {x['mean']:+.1f} pp (n={x['n']})" for x in res["by_bin"]),
            f"  Q5 - Q1 = {res['spread_q5_minus_q1']['diff']:+.1f} pp, 95% CI "
            f"{res['spread_q5_minus_q1']['ci_low']:+.1f} to {res['spread_q5_minus_q1']['ci_high']:+.1f}, "
            f"p = {res['spread_q5_minus_q1']['p']:.2f} (Welch; filings treated as independent)",
        ]],
        "",
        "ALL FIRMS COMBINED: EQUAL-WEIGHTED BIN BASKETS (T6)",
        f"Filing years: {(pl.get('baskets_years') or ['?', '?'])[0]}-{(pl.get('baskets_years') or ['?', '?'])[1]}; "
        "cumulative return ahead of the S&P 500 over the same windows:",
        "  " + ", ".join(f"Q{b} {(v - 1) * 100:+.0f}%" for b, v in (pl.get("baskets_final_relative") or {}).items()),
        "",
        f"Reminder: {s.get('rows', '?')} scored filings from {n_firms} hand-picked firms illustrate the",
        "pipeline; they are not evidence for or against the Lazy Prices effect.",
    ]
    text = "\n".join(out) + "\n"
    cfg.paths.outputs.mkdir(parents=True, exist_ok=True)
    cfg.paths.coverage.write_text(text)
    print(text)
    return text
