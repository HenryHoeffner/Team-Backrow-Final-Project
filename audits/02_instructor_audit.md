# Instructor audit: Team Backrow, Checkpoint 2

**Repo:** HenryHoeffner/Team-Backrow-Final-Project · **Audited commit:** `d8d28d2` (2026-11-14 21:38, tip of the default branch `restructure-run-order`) · **Project:** replicate *Lazy Prices* (Cohen, Malloy & Nguyen 2020) on a 20-firm pilot

> Note from your human teacher: This review is generated with minimal supervision from Opus 5.5-high. It is thorough, but can be too generous at times and doesn't know my taste for what is "good". Grades it and I would assign are correlated, but noisy, ok? If you want additional feedback from _me_, you need to find me before/after/during class or during office hours for a guaranteed speedy reply. I will try to respond to emails and issues, but can not respond to student inquiries around the clock across the final weeks of class. Response times will be unpredictable, though during Thanksgiving week, I will do my best to respond quickly virtually, as in person options will be nil.

## Summary

The pilot is well engineered:
- clear definitions;
- a firm-relative change score that uses only earlier years;
- a return clock that starts after the filing month;
- 43 unit tests that pass;
- a committed results snapshot.

From that snapshot I independently reproduced every bin, the pooled B5 − B1 (+6.72 pp, Welch p = 0.46) and all 140 full-window returns. I couldn't rerun the download-to-score steps (they need about 10 GB of SEC filings, not available in the audit environment). The main issues:
1. Two required files are missing (A1).
2. The sample is 20 of today's large firms (A2).
3. The test treats firm-years as independent (A3).

| Check | Result |
|---|---|
| Reruns from scratch | ⚠️ `pytest`: 43 passed, 2 skipped (both need `data/`). Steps T1–T7 need SEC EDGAR, not available here. `data/` (similarity, prices) isn't committed (A4) |
| Inputs have provenance | ✅ CIKs, accession numbers and amendments dropped are listed in `app_data/coverage.txt` |
| Keys unique, merges validated | ⚠️ your self-audit #12: one merge in `t4_bins.py` lacks `validate=` |
| No look-ahead / survivorship | ✅ look-ahead (filing-month clock, prior-years-only score). ❌ survivorship in firm selection (A2) |
| LLM leakage handled | n/a |
| `specs_tried.md` complete | ❌ missing (A1) |
| Magnitudes discussed | ⚠️ the +6.7 pp spread with a CI, no costs or beta adjustment yet (your #8) |
| Hand checks | ✅ unit tests recompute cosine similarity, bins, windows and CIs |
| Threats to validity | ⚠️ in the proposal and the dashboard's Methodology tab, not in the README |
| Every number traces to `outputs/` | ✅ the dashboard reads `app_data/`, whose numbers reproduce |

## What holds up

- **Bins:** re-ranked from `rel_change` within each fiscal year (descending, ties alphabetical, `ceil(5·rank/n)`), 0 of 160 differ from `bin_relative` in `app_data/firm_years.csv`.
- **Headline spread:** pooled full-window firm-years (n = 140; B1 n = 28, mean −4.575; B5 n = 28, mean +2.147), B5 − B1 = 6.7215 pp, Welch p = 0.4636. This matches `app_data/plot.json`.
- **Returns:** a fresh yfinance pull of month-end adjusted closes reproduces `firm_return_pct` and `spy_return_pct` for all 140 full windows (max difference 0.000 pp). This is the same source, re-pulled; a different-source check is still open (your self-audit #8).
- **No look-ahead in the signal:** `prior_median_change` uses only earlier years, and the 12-month window starts at the end of the filing month.

## Findings

### A1 · Major · Required files are missing or misplaced

**Evidence:**
- There is no `STATUS.md` and no `specs_tried.md` on any branch (searched all refs).
- The proposal is at `proposal/proposal.md`, not `PROPOSAL.md`, and still contains the template's prompt text (lines 1–9: "The unit of observation: what one row is…").
- The repo has no `main` branch. The GitHub default branch is `restructure-run-order`.
- The README has no threats-to-validity section (the threats are in the proposal, §4, and the dashboard).

**Fix:**
- Add `STATUS.md` (CP1 memo plus current status).
- Add `specs_tried.md`, listing at least `bin_basis` firm-relative vs raw, `relative_min_history` = 2, cosine vs Jaccard, and Items 1A + 7 combined vs separate, with what each gave.
- Move the proposal to `PROPOSAL.md` and delete the template prompts.
- Rename the default branch to `main`.
- Add a "Threats to validity" section to the README.

**How to show it's fixed:** The files exist on `main`, and `specs_tried.md` lists the choices in `config.yaml`.

### A2 · Major · The 20 firms are today's large survivors

**Evidence:** README "Scope and decisions": "Twenty hand-picked large firms", each required to have an original 10-K for every year FY2015–FY2025 (`config.yaml`). So every firm survived and stayed large through 2025.

**Why it matters:** Lazy Prices is a cross-sectional return prediction. Picking firms that you know survived, and that file through 2025, removes the failures and acquisitions where heavy 10-K changes (restructurings, distress) are most likely to be followed by bad returns. That could bias B1 upward and shrink the spread. You note it's "not a random sample", but the proposal's threats don't name survivorship.

**Fix:** For v1, define the universe at each filing date: e.g. all firms in a point-in-time index, or all 10-K filers above a size cutoff that year, without requiring future filings. Keep firms that later delist, and take their returns through the delisting (a CRSP delisting return, or the last price plus the deal value). Log the universe rule in `specs_tried.md`.

**How to show it's fixed:** The README states a point-in-time universe rule, and the coverage report lists firms that drop out after their last filing.

### A3 · Minor · The B5 − B1 test treats firm-years as independent

**Evidence:**
- The pooled Welch test in `t6_plot.py` (README "Pooled graph") compares 28 B1 firm-years with 28 B5 firm-years.
- Firms in the same filing year share the market's 12-month return, and each firm appears up to seven times.
- `all_firms_combined.png` already builds yearly B1/B5 baskets.

**Why it matters:** Correlated observations make the CI too narrow. Cohen, Malloy & Nguyen test with calendar-time portfolios for this reason.

**Fix:** Make the main test the time series of yearly basket differences (B5 basket − B1 basket, 7 values) with a t-test on its mean, or add year fixed effects and clustering by firm and year. Keep the pooled Welch test as descriptive.

**How to show it's fixed:** `plot.json` reports the basket-difference test.

### A4 · Minor · Commit the small intermediate files so later steps rerun without SEC

**Evidence:**
- `.gitignore` excludes all of `data/`, so `data/similarity.parquet`, `data/prices_monthly.csv` and `data/reports/` aren't in the repo.
- `tests/test_dashboard.py:61,90` skip without them.
- Rerunning T4–T7 requires downloading about 10 GB of filings first (README).

**Fix:** Commit `data/similarity.parquet` (one row per firm-year) and `data/prices_monthly.csv` with their pull dates. Add a `make from-scores` target that runs T4–T7 from them. Keep the raw filings ignored.

**How to show it's fixed:** On a fresh clone, `make from-scores && make test` runs with no skips.

## How to respond

This audit is `audits/02_instructor_audit.md` in your repo. Fix what you can, then add `audits/03_audit_response.md`, replying to each finding ID: fixed (the commit), disputed (why), or disclosed as a limitation (where).

**Deadline: Saturday, November 21, 2026.**
