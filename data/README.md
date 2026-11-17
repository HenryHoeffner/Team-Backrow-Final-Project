# Committed intermediate files

Everything else in `data/` is git-ignored (raw filings, clean text and sections are about 10 GB). These files are committed so steps T4–T7 rerun on a fresh clone without downloading from SEC EDGAR:

```bash
make setup
make from-scores   # T4 bins, T5 returns, T6 plots, T7 coverage, snapshot
make test          # no skips
```

| File | Written by | What it is | Pulled |
|---|---|---|---|
| `similarity.parquet` | T3 (`make score`), bin columns added by T4 | One row per firm-year (200): cosine and Jaccard similarity of Item 1A + Item 7 to the prior-year 10-K, per-section cosine and word counts | 10-Ks downloaded from SEC EDGAR and scored on 2026-11-11 |
| `prices_monthly.csv` | T5 (`make returns`) | Month-end adjusted closes (`date, ticker, adj_close`) for the 20 firms and SPY, through October 2026 | Downloaded from Yahoo Finance (`yfinance`) on 2026-11-11 |
| `reports/download.json` | T1 | Filings found, amendments dropped, gaps | 2026-11-11 |
| `reports/clean.json` | T2 | Clean-file and section word counts, sections taken from exhibits, outliers | 2026-11-11 |
| `reports/score.json` | T3 | Rows scored, gaps, lowest-similarity filings | 2026-11-11 |

T7 (`make coverage`) reads the three reports, so the coverage report on a fresh clone matches the full run.

T5 uses `prices_monthly.csv` as long as it covers every ticker and window, so `make from-scores` reproduces the committed results exactly. `python -m pilot returns --refresh` pulls new prices from Yahoo, which can change the results; if you commit refreshed prices, update the date above.

After `make all` (the full run from SEC), commit these files again together with `app_data/`.
