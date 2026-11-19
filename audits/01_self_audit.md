# Self-audit 1 (Checkpoint 2)

**Date:** 2026-11-14  
**Repo state reviewed:** `restructure-run-order` at commit `205f121` (pipeline, charts and Streamlit dashboard)  
**How:** the course's *Skeptical review* prompt, run with a coding agent: "Review this repo like a skeptical finance professor. Look for look-ahead bias and leakage, merges without validate, unit and frequency mismatches, hard-coded paths or keys, and steps that don't reproduce from run_all.py. List issues ranked by severity; don't fix anything yet." Each finding below was then checked against the code and the pipeline's output files.

## 1. What it flagged, and which findings are real

| # | Severity | Finding | Real? |
|---|---|---|---|
| 1 | High | The return window starts on the filing day for 10 of 160 filings (AMZN, BA ×4, GOOGL, INTC, META, NEM, PFE). `compute_window` in `src/pilot/t5_returns.py` only moves the start to the next month when the filing date is *after* the month's last trading day. A 10-K filed after the close on that day is "bought" at a close before it was public, so the window includes the reaction to the filing. | **Real.** All 10 confirmed in `data/returns.parquet`. Whether each was filed after the close still needs checking against the SEC acceptance time, but the rule doesn't prevent it. The T5 check (`window_start >= filing_date`) lets equality through. |
| 2 | High | Bins rank all firms within a fiscal year (`src/pilot/t4_bins.py`), but filing dates in a year are 28–38 days apart. An early filer's bin depends on scores of firms that filed up to a month later. The basket chart "starts" in January with baskets only known in March. | **Real.** Probably a small effect, but it is look-ahead. The paper sets cutoffs from earlier filings. |
| 3 | High | Survivorship: the 20 firms were chosen in 2026 and had to file every 10-K through FY2025. Delisted, acquired or bankrupt firms can't be in the sample, and free Yahoo prices have no delisting returns. | **Real.** Already disclosed in the README. Prices now come from CRSP with Shumway delisting returns, but the 20-firm sample is still survivor-only. |
| 4 | High | README numbers don't match current outputs: "INTC is B1 in 6 of 10 years on raw similarity" (`data/reports/bins.json`: 8) and "PFE is B1 in 4 of 8 years" (now 3). `pyproject.toml`, `src/pilot/__init__.py` and `src/pilot/t2_sections.py` still say "five firms". | **Real.** Checked against `data/reports/bins.json`. |
| 5 | High | Required files missing: `specs_tried.md`, `STATUS.md`, `audits/`. The switch from raw-similarity to firm-relative bins was made after seeing INTC sit in B1 most years; the sample also grew from 5 to 20 firms and a heatmap graphic was dropped. None of this is logged. No `run_all.py` (the README's `make all` steps cover it, but `make` isn't standard on Windows). | **Real.** |
| 6 | Medium | Yahoo encoded spin-offs as non-standard "splits" (prices now come from CRSP, where spin-offs are distributions in `ret`), and nothing checks them. Spin-offs inside full return windows likely include HON/Solstice (Oct 2025), PFE/Viatris (Nov 2020) and MRK/Organon (Jun 2021). | **Plausible, not yet verified.** HON's odd 0.9535 factor (Jun 2026) is confirmed; the other events need checking. |
| 7 | Medium | The Welch t-test treats 140 filings as independent. Windows in the same year end within about five weeks of each other and share market shocks, and each firm appears seven times, so the confidence intervals are too narrow. | **Real.** Doesn't change the conclusion (p = 0.46 is already not significant). |
| 8 | Medium | Outliers drive the bin means: NEM +192, META +150, INTC +123 pp. B4 mean +9.2 vs median +3.2; B3 mean +4.9 vs median −4.9. On medians B5 − B1 is about +2 pp, not +6.7. | **Real.** Confirmed from `data/returns.parquet`. |
| 9 | Medium | The basket chart (`bin_baskets` in `src/pilot/t6_plot.py`) compounds 12-month holds as if they ran back to back, but they overlap or leave gaps of up to about five weeks, so it isn't an investable series. Its "+19 points" is relative wealth, a different unit from the pooled chart's pp per year. | **Real.** The chart is labelled illustrative. |
| 10 | Medium | Formatting changes score as rewrites: PFE moved its MD&A from an exhibit into the 10-K (FY2020) and HON redesigned its 10-K (FY2020). Part of the signal measures layout, not news. | **Real.** Already disclosed. |
| 11 | Medium | Reruns aren't identical, though the README says they are: `data/` is git-ignored, so a clean clone downloads prices fresh; `drop_incomplete_month(date.today())` and Yahoo's revisions made results depend on the run date (prices now come from the fixed CRSP files); pipeline packages are only lower-bound pinned; `src/pilot/t1_download.py` patches a private function inside `sec-edgar-downloader`. | **Real.** |
| 12 | Low | One merge has no `validate=`: `src/pilot/t4_bins.py` line 77. | **Real, harmless today** (keys are unique). Every other merge is validated. |
| 13 | Low | `run_clean` never clears `data/sections/`, so a filing that stops parsing keeps its old section files and is still scored. `make snapshot` copies whatever `outputs/coverage.txt` is on disk. | **Real, minor.** |
| 14 | Low | Section-heading rules in `src/pilot/t2_sections.py` are tuned per firm, and `filed_after` assumes December year-ends. | **Real.** Acceptable for the pilot; won't scale to a full sample. |
| 15 | Low | FY2018 bins compare against a firm's median change over only two earlier years. | **Real.** A design choice; noisy. |
| 16 | Low | Year labels differ: the pooled chart says FY2018–FY2024, while the other charts and the dashboard use filing years 2019–2026. | **Real.** Cosmetic. |

**Checked and fine:** firm-relative change uses only earlier years (`shift(1)` in `firm_relative_change`); no hard-coded paths or API keys (the SEC identity comes from environment variables); no LLM in the signal; partial windows are left out of all statistics; 10-K/A amendments are dropped and listed; the merges in `t6_plot.py` and `dashboard.py` use `validate=`.

## 2. What was fixed, and what's still open

**Fixed in this PR:** nothing. This PR records the review; fixes come in the next ones.

**Open, with the plan:**

| # | Plan |
|---|---|
| 1 | Start the window at the next month-end whenever the filing date is on or after the month's last trading day; make the T5 check strict (`>`). Read the SEC acceptance time from each filing header to confirm which of the 10 were after the close. |
| 2 | Set bin cutoffs from the previous year's distribution of scores, so each filing is binned the day it is public. Keep within-year ranking as a robustness check and log both in `specs_tried.md`. |
| 3 | Full project: a point-in-time S&P 500 member list. Until then, keep it under threats to validity. |
| 4 | Correct the README numbers and the "five firms" text; add a test that fails when a number quoted in the README doesn't match `data/reports/`. |
| 5 | Add `specs_tried.md` (raw vs firm-relative bins, 5 vs 20 firms, sections scored, dropped heatmap, every pooled spec) and `STATUS.md`. Merge the teammate's `run.py` (one-command run) or add `run_all.py`. |
| 6 | Flag every non-standard split ratio in the coverage report; check each against the company's 8-K or IRS Form 8937; rerun with affected windows dropped and report whether B5 − B1 moves. |
| 7, 8 | Report medians and trimmed means next to means; cluster confidence intervals by year. |
| 9 | Keep the basket chart labelled illustrative; for the full project, replace it with monthly calendar-time portfolios (the paper's test). |
| 10 | Report results with PFE FY2020 and HON FY2020 excluded as a robustness check. |
| 11 | Commit the monthly price file with its download date; pin pipeline package versions; replace "identical outputs" in the README with an accurate statement. |
| 12, 13 | Add `validate="one_to_one"`; clear stale section files before each clean run. |
| 14–16 | Leave for the pilot; make the year labels consistent when the charts are next touched. |

## 3. Checklist (top of `00_PROJECT_SEEDS`)

1. **It reproduces:** problem. `make all` rebuilds everything from raw, but there's no `run_all.py`, README numbers are stale (#4), and fresh price downloads change results (#11).
2. **Every input has a provenance:** problem. SEC download code, `filings_manifest.csv` and `form_audit.csv` are there; filing download dates aren't recorded and the price file isn't committed.
3. **Unit of observation:** OK with one gap. One row is a firm's 10-K for a fiscal year; duplicates are removed in T1 and merges validated, except `t4_bins.py` line 77 (#12).
4. **No look-ahead:** problem. Filing-day windows (#1), ranking against later filers (#2), survivorship (#3).
5. **No LLM leakage:** OK. No LLM is used in the signal or the pipeline.
6. **No p-hacking:** problem. No `specs_tried.md` yet (#5).
7. **Magnitudes, not just stars:** not yet. +6.7 pp a year is reported with its 95% range, but no trading costs, no factor-adjusted alpha and no median-based check (#8).
8. **Checks by hand:** partly OK. Unit tests recompute cosine similarity, bin assignment, return windows and confidence intervals by hand; no real return has been checked against a second source yet.
9. **Honest limits:** problem, minor. The README has "Known limitations"; it should be renamed "Threats to validity" and add #1, #2 and #6.
10. **You understand it:** not yet. Each teammate should be able to walk through every step, including the parts an agent wrote.
