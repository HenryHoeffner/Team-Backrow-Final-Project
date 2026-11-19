# Committed intermediate files

Everything else in `data/` is git-ignored (raw filings, clean text and sections are about 10 GB). These files are committed so steps T4–T7 rerun on a fresh clone without downloading from SEC EDGAR. T5 also needs the two CRSP files, which are licensed and never committed: get your own copy as described in [`README_DATA.md`](../README_DATA.md) and put them in `data/`.

```bash
make setup
make from-scores   # T4 bins, T5 returns, T6 plots, T7 coverage, snapshot
make test          # no skips
```

| File | Written by | What it is | Pulled |
|---|---|---|---|
| `similarity.parquet` | T3 (`make score`), bin columns added by T4 | One row per firm-year (200): cosine and Jaccard similarity of Item 1A + Item 7 to the prior-year 10-K, per-section cosine and word counts | 10-Ks downloaded from SEC EDGAR and scored on 2026-11-11 |
| `reports/download.json` | T1 | Filings found, amendments dropped, gaps | 2026-11-11 |
| `reports/clean.json` | T2 | Clean-file and section word counts, sections taken from exhibits, outliers | 2026-11-11 |
| `reports/score.json` | T3 | Rows scored, gaps, lowest-similarity filings | 2026-11-11 |

T7 (`make coverage`) reads the three reports, so the coverage report on a fresh clone matches the full run.

T5 builds `data/prices_monthly.csv` (a monthly return index per firm, compounded from CRSP `ret_adj`) from the CRSP files and keeps it as a local cache. It is git-ignored because it is CRSP data in another form. Everyone with the same CRSP files gets the same results.

After `make all` (the full run from SEC), commit these files again together with `app_data/`. Never commit the CRSP files or `prices_monthly.csv`; `make check-data` and the pre-commit hook (`make hooks`) catch it.
