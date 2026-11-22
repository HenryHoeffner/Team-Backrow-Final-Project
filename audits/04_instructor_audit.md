# Instructor audit: Team Backrow, Checkpoint 3

**Repo:** HenryHoeffner/Team-Backrow-Final-Project · **Audited commit:** `9d451fb` (2026-11-19, `main`, merge of PR #17) · **Seed:** "From earlier terms": replicate *Lazy Prices* (Cohen, Malloy & Nguyen, 2020), with the generic checklist and your `PROPOSAL.md` · **CP2 audit:** `audits/02_instructor_audit.md` (commit `d8d28d2`)

> Note from your human teacher: This review is generated with minimal supervision from Opus 5.5-high. It is thorough, but can be too generous at times and doesn't know my taste for what is "good". Grades it and I would assign are correlated, but noisy, ok? If you want additional feedback from _me_, you need to find me before/after/during class or during office hours for a guaranteed speedy reply. I will try to respond to emails and issues, but can not respond to student inquiries around the clock across the final weeks of class. Response times will be unpredictable, though during Thanksgiving week, I will do my best to respond quickly virtually, as in person options will be nil.

## Summary

The pipeline is careful, and what can be rerun here reproduces.
- The bins rebuild identically from the committed `data/similarity.parquet`.
- My own code reproduces the new yearly-basket test exactly.
- Your switch to CRSP passes a second-source check: yfinance gives the same 12-month returns within 0.9 pp for all 95 full windows.
- `main` now exists, with `STATUS.md`, `specs_tried.md`, `PROPOSAL.md` and a README threats section, so all four CP2 findings are fixed or disclosed.

But v1 is still the 19 hand-picked survivors, not a full sample (B1). That matters most. The README's threats section still quotes the yfinance-era numbers (B2).

## Follow-up on your Checkpoint 2 audit

Response file: not found. The statuses below come from the repo itself.

| CP2 finding | Status | Evidence |
|---|---|---|
| A1 · Required files missing or misplaced | fixed | Commit `1ba7072`. `STATUS.md`, `specs_tried.md` and `PROPOSAL.md` exist at the root of `main`, and `PROPOSAL.md:1-9` has no template prompts. The GitHub default branch is now `main` (`git remote show origin`: "HEAD branch: main"). `README.md:261` "Threats to validity". `specs_tried.md` lists the `config.yaml` choices (bin basis, `relative_min_history`, cosine vs Jaccard, Item 1A/7) with their results |
| A2 · Today's large survivors | disclosed | README "Sample and selection" → "Survivorship" states the problem and its likely direction, with a planned point-in-time fix. `data/sp500_proxy.py` (a size-based point-in-time universe from CRSP) exists but isn't used by the pipeline yet. The sample is still 19 firms (B1) |
| A3 · B5 − B1 test treats firm-years as independent | fixed | Commits `50f572a`, `a66eeaf`. `app_data/plot.json` → `pooled.bin.basket_spread_test`: +10.77 pp, SE 19.98, p = 0.618, 5 years. My own recomputation from `app_data/firm_years.csv` gives the same (below) |
| A4 · Commit small intermediate files | fixed | `data/similarity.parquet` (190 × 19) and `data/reports/{download,clean,score}.json` are committed. `python -m pilot bins` on a fresh copy rebuilds `similarity.parquet` identically (`DataFrame.equals` True), with no SEC download. Prices are now CRSP, which can't be committed (`README_DATA.md`), so T5–T7 need the course CRSP files, and 2 dashboard tests skip without them. That is not counted against you |

**3 of 4 fixed, 0 still open (1 disclosed).**

## Checkpoint 3 checks

| Check | Result |
|---|---|
| Reruns from scratch (full sample) | ❌ not a full sample (B1). On the 19 firms: T4 ✅ identical. T1–T3 need SEC (not rerun), and T5 needs your CRSP files (not available here) |
| Inputs have provenance | ✅ `README_DATA.md` (CRSP pull date, tables, filters, Shumway rule), `data/reports/*.json`, `app_data/coverage.txt` |
| Keys unique, merges validated | ✅ T4 checks printed on every run (19 firms per year, `ceil(5*rank/n)`, no ties) |
| No look-ahead / survivorship | ⚠️ the signal and the timing are fine. Survivorship is disclosed but not fixed (A2, B1) |
| LLM leakage handled | n/a |
| `specs_tried.md` complete | ✅ the order of decisions from git history, and 9 specifications with results |
| Magnitudes discussed | ⚠️ +10.8 pp a year with a −44.7 to +66.2 CI. Beta adjustment is planned (README threats), not done |
| Hand checks | ✅ unit tests recompute similarity, bins, windows and tests (51 passed, 3 skipped; `test_licensing.py` 4/4 with git present) |
| Threats to validity | ✅ thorough README section, but some numbers are stale (B2) |
| Every number traces to `outputs/` | ⚠️ the headline, `specs_tried.md` and the dashboard match `plot.json`. README threats don't (B2) |
| Dashboard matches `outputs/` | ✅ "B5 beat B1 by +10.8 pp a year … (p = 0.62)" = `plot.json` `basket_spread_test` |

Steps not rerun by design: T1–T3 (`make download`/`clean`/`score`), which use SEC EDGAR, since the audit makes no SEC requests. T5 needs CRSP files the repo correctly doesn't contain. I started from the committed `data/similarity.parquet` and `app_data/`. These are not counted against you.

## Getting ready for Dec 1

Presentations run only from URLs, with a hard cutoff at 9 minutes (10:45 section) or 10 minutes (12:10 section). Put your URL(s) in column G of the Team Projects sheet.

| Check | Result |
|---|---|
| Dashboard launches from a clean clone | ✅ in a venv built from `requirements.txt` only (what Streamlit Cloud installs): `streamlit run app.py --server.headless true --server.port 8602` on a clean export of `9d451fb`. `/_stcore/health` returned `ok` after 3 s. A headless browser clicked all 4 tabs, with no exceptions on the page or in the log |
| Dashboard shows the v1 numbers from `outputs/` | ✅ it reads the committed `app_data/` snapshot. "+10.8 pp", "p = 0.62" and the −44.7 to +66.2 range match `plot.json` |
| README links the live URL(s) | ✅ `README.md:3` links the `…streamlit.app` dashboard (the live site itself wasn't checked) |

**Core story for 9–10 minutes:** the signal (firm-relative change in Items 1A + 7) with one sentence-diff example; the bin chart; the yearly-basket result with its interval, said plainly ("right direction, not distinguishable from zero"); then what the full sample (B1) changes. The specification table can be one slide.

## What holds up

- **Bins reproduce exactly** from the committed similarity file (`python -m pilot bins`, 1.4 s). My own re-ranking (`rel_change` descending within fiscal year, `ceil(5·rank/n)`) agrees on all 114 binned firm-years.
- **Basket test, independently.** From `app_data/firm_years.csv` (full windows only), the yearly B5 − B1 differences are 2019 +5.53, 2020 +16.90, 2021 −27.19, 2022 −24.49, 2023 +83.10. Their mean is +10.768 (SE 19.976, t₄ p = 0.6185), as in `plot.json`.
- **CRSP returns, checked against a second source.** yfinance adjusted closes at each window's start and end give the same 12-month firm return for 94 of 95 full windows within 0.5 pp (median difference 0.03 pp, max 0.88 pp, PFE FY2019, a window your threats list flags for the Viatris spin-off). The CRSP benchmark (sprtrn plus the market dividend yield) is within 0.53 pp of SPY's total return in every window.
- **Honest reporting.** `specs_tried.md` records what you had seen before each choice ("Returns … had already been computed, so we can't prove they played no role"), keeps the headline fixed, and says none of the nine specifications is significant.
- **A pre-commit check that blocks committing CRSP data** (`make check-data`, `tests/test_licensing.py`).

## New findings

### B1 · Blocking · v1 is still the 19 hand-picked firms

**Evidence:** `config.yaml` and `app_data/firm_years.csv`: 19 tickers, 114 firm-years, 95 with full windows. `STATUS.md` ("Next: … then the v1 full sample") and README "Small, hand-picked sample" say so too. The headline test has 5 yearly observations, with B1 at 3 firms a year (`specs_tried.md` §2).

**Why it matters:** Checkpoint 3 was v1 on the full sample. With 3–4 firms per bin per year, no specification can distinguish the effect from zero (your own words: "none of this is evidence either way"). The survivorship problem (A2) can only be fixed with a larger, point-in-time universe.

**Fix:** Use `data/sp500_proxy.py` (already written) to define the universe at each filing date, and run T1–T7 on it. Download sizes will grow, so start with one or two years if needed. Keep firms that later delist, which your CRSP `ret_adj` already handles. Log the universe rule in `specs_tried.md` before running.

**How to show it's fixed:** `firm_years.csv` covers the point-in-time universe, and `coverage.txt` lists firms that drop out after their last filing. I will rerun T4 from the committed similarity file and recompute the basket test.

### B2 · Minor · README threats still quote the yfinance-era numbers

**Evidence:**
- `README.md:269`: "B5 − B1 is +5.4 pp on raw bins vs +6.7 pp firm-relative". `specs_tried.md` §2 now has +8.14 and +10.77.
- `README.md:274`: "200 scored filings (160 binned) from 20 large, stable firms". `firm_years.csv` has 19 firms and 114 binned firm-years.
- `README.md:296`: "NEM +192, META +150, INTC +123 pp … on medians B5 − B1 is about +2 pp, not +6.7". On the current file, the largest full-window excess returns are META +149.8, COP +71.3 and AMZN +56.9, and the median B5 − B1 is +3.2 pp against a mean of +10.8.
- `README.md:1` and `PROPOSAL.md:1` still say "20 firms".

**Fix:** Regenerate these numbers from `plot.json` and `firm_years.csv` (or have the snapshot step write them), and correct the firm count.

**How to show it's fixed:** Every number in the README matches a committed file.

### B3 · Minor · Check why AMT has "no CRSP data after 2011"

**Evidence:** Commit `e5d0ca1` and README "CRSP coverage": AMT is excluded because it "has no data after 2011" under the SHRCD 10/11, price ≥ $1 filters. American Tower restructured as a REIT holding company in early 2012. I can't check CRSP here (**not verified**), but a reorganization like that can come with a new PERMNO, or a share-code change outside 10/11.

**Why it matters:** Dropping a firm because of an identifier change is a quiet sample-selection choice. In the full sample (B1), the same rule would drop every firm that reorganized.

**Fix:** Look up AMT's PERMNOs and SHRCD history in `msenames` around 2012. If it continues under a new PERMNO, link by PERMCO, as `sp500_proxy.py` already does. Otherwise, document the share code.

**How to show it's fixed:** AMT is back in, or the README states the specific reason.

## How to respond

This audit is `audits/04_instructor_audit.md` in your repo. Fix what you can, then add `audits/05_audit_response.md`, replying to each **B** finding (no CP2 findings are still open; A2's survivorship is carried by B1): fixed (the commit), disputed (why), or disclosed as a limitation (where).

There's no separate deadline for this response. Keep working through these until your final deliverables are due: the final repo is audited again then.
