# CRSP monthly stock data

Pulled from WRDS on 2026-11-13 with legacy CRSP monthly tables (`crsp.msf`, `msenames`, `msedelist`, `msi`). Code: `pull_crsp_monthly.do` (WRDS pull) and `make_parquet.py` (filters, Shumway rule, parquet).

## Sample

- NYSE (EXCHCD 1), AMEX (2) and NASDAQ (3) common stocks, SHRCD 10 or 11. Exchange and share code are taken as of each month from the CRSP names history, so a stock appears only in months when it met the filters.
- Month-ends from 2000-01 through 2024-12 (end of the legacy CRSP monthly file).
- Rows with a price below $1 are dropped, as are rows with a missing price. The price is `abs(prc)` at that month-end. This filter also removes some delisting months of penny stocks, so the sample is slightly more favorable than the full population.
- Result: 1,232,467 rows, 12,774 PERMNOs, no duplicate PERMNO-month rows. Exchange counts: NASDAQ 749,055, NYSE 410,308, AMEX 73,104.

## Files

Both files go in `data/`, which git ignores, so they are never committed. Each teammate gets their own copy from the course or WRDS.

| File | Contents |
|---|---|
| `crsp_monthly_nyse_amex_nasdaq_2000plus.parquet` | The stock-month panel |
| `crsp_monthly_market.csv` | CRSP index returns and market totals by month, 2000 on (300 months) |

## Columns that were added or changed

| Column | Meaning |
|---|---|
| `prc` | **Absolute value of CRSP PRC.** CRSP stores a bid/ask midpoint as a negative number on days with no closing trade. |
| `prc_raw` | The original CRSP PRC, signed |
| `mktcap` | `prc * shrout`, in thousands of dollars |
| `dlret_filled` | Delisting return after the Shumway rule (below) |
| `dlret_shumway` | True when `dlret_filled` was imputed (3,541 rows) |
| `ret_adj` | **Return including delistings.** Use this for returns. |

## Shumway (1997) delisting rule

CRSP `ret` does not include delisting returns. For each delisting month:
- If CRSP supplies `dlret`, use it.
- If `dlret` is missing and the delisting code is performance-related (500, 520-584), use -30%.
- If `dlret` is missing and the code is anything else (mergers, exchanges, liquidations), use 0%. Code 100 (still trading at the end of the file) is also treated as 0%.

Then `ret_adj = (1 + ret) * (1 + dlret_filled) - 1`. If `ret` is missing in the delisting month, `ret_adj = dlret_filled`. Months without a delisting have `ret_adj = ret`. The original `ret`, `retx`, `dlret` and `dlretx` are kept unchanged. 6,298 rows have a missing `ret_adj`, mostly the first month of a listing.

The -30% figure comes from Shumway's NYSE/AMEX evidence. Shumway and Warther (1999) argue for a larger loss, about -55%, for NASDAQ performance delistings. Check that the results hold under that alternative before relying on the NASDAQ rows.

## Other notes

- `cusip` is the 8-character CUSIP as of the date and is never missing. `ncusip` is CRSP's NCUSIP and is often blank. Both are stored as text.
- The share price/share adjustment factors (`cfacpr`, `cfacshr`) are included for adjusting prices across splits.
- Not applied: any market-cap filter, minimum listing history, or exclusion of financials and utilities.

## Licensing

CRSP data is licensed to Lehigh users. Do not post the raw files in a public repository or in anything people can download. Aggregated results are fine.

This repo is public, so anything committed is published. The two CRSP files stay in `data/` on each teammate's laptop, and so do the files the pipeline builds from them: `data/prices_monthly.csv` (a monthly return index per firm), `data/prices_monthly.source.txt` and `data/returns.parquet`. All of these are git-ignored. Results computed from CRSP, such as `app_data/`, the coverage report and the figures, are committed.

To keep it that way:

- **Pre-commit hook.** Run `make hooks` once per laptop (`make setup` also does it). After that, `git commit` refuses to commit any of the files above, any data file with "crsp" or "wrds" in its name, or any table with CRSP columns (`permno`, `ret_adj`, `dlret`, `vwretd`, ...) or price/return-series columns (`adj_close`, `prc`, `ret`).
- **Check.** `make check-data` runs the same check, and `make test` includes it (`tests/test_licensing.py`).

The check can't recognize CRSP numbers saved under other column names. Any new code that reads CRSP must write its output to git-ignored files.
