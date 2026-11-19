# Specifications tried

Every specification we have run, not only the one we report. The headline is the setting in `config.yaml`. Each alternative below changes one choice and keeps everything else the same.

## 1. How the headline specification got here

The order in which choices were made, from the git history.

| Date | Commit | Change | Why | Seen before deciding |
|---|---|---|---|---|
| Nov 6 | `176970a`–`7f19075` | First version: 5 firms (INTC, PFE, JPM, MCD, CAT), FY2020–2025, whole 10-K, cosine similarity, bins ranked on raw similarity | Proof of concept | Nothing yet |
| Nov 7 | `6ba8c8d` | Score Item 1A (Risk Factors) + Item 7 (MD&A) only; extend to FY2015–2025 | The paper's strongest results come from these sections; whole-10-K scores mix in boilerplate and financial tables. More years give each firm a history | Similarity scores |
| Nov 7 | `1a0ffb0` | Bin on change relative to the firm's own earlier years (`bin_basis: firm_relative`, `relative_min_history: 2`) instead of raw similarity | On raw similarity INTC was in B1 in 6 of 10 years, so bins ranked firms by writing style, not events | Bin counts. Returns (T5, `6f6c549`) had already been computed, so we can't prove they played no role |
| Nov 7 | `26b2ef6` | Returns in excess of SPY instead of raw returns | The claim is about returns relative to the market | Returns |
| Nov 7 | `ceb008f` | 5 → 20 firms across 10 sectors | Five firms are too few for any pooled comparison | Results on 5 firms |

The raw-similarity bins (`bin_raw`) have been kept and reported next to the headline since `1a0ffb0`, in `app_data/plot.json` and the dashboard's switch.

## 2. Results under each specification

B5 − B1 in 12-month excess return over the S&P 500 (CRSP), percentage points. Full return windows only. The test is a t-test on the yearly B5 − B1 basket differences: each filing year's B5 basket average minus its B1 basket average, one number per year, because firm-years in the same year are not independent (self-audit #7). The pooled Welch p-value, which treats every firm-year as independent, is kept as a descriptive column.

| Specification | Years | B1 n | B5 n | B1 mean | B5 mean | B5 − B1 (pp) | 95% CI (yearly baskets) | p (yearly baskets) | Welch p (descriptive) |
|---|---|---|---|---|---|---|---|---|---|
| **Headline:** cosine, Item 1A + 7 combined, firm-relative, `relative_min_history: 2` | FY2018–FY2022 | 15 | 20 | −7.96 | +2.81 | **+10.77** | −44.7 to +66.2 | 0.62 | 0.35 |
| Raw similarity bins (`bin_basis: raw`), same years as headline | FY2018–FY2022 | 15 | 20 | −2.86 | +5.28 | +8.14 | −28.3 to +44.5 | 0.57 | 0.47 |
| Raw similarity bins (`bin_basis: raw`), all scored years | FY2016–FY2022 | 21 | 28 | +0.52 | +3.62 | +3.10 | −20.6 to +26.8 | 0.76 | 0.71 |
| Firm-relative, `relative_min_history: 1` | FY2017–FY2022 | 18 | 24 | −7.85 | +0.88 | +8.73 | −33.5 to +51.0 | 0.62 | 0.37 |
| Firm-relative, `relative_min_history: 3` | FY2019–FY2022 | 12 | 16 | −9.02 | +3.06 | +12.08 | −69.8 to +94.0 | 0.67 | 0.39 |
| Jaccard instead of cosine, firm-relative | FY2018–FY2022 | 15 | 20 | −12.78 | −6.67 | +6.11 | −12.0 to +24.2 | 0.40 | 0.43 |
| Jaccard instead of cosine, raw | FY2016–FY2022 | 21 | 28 | −5.64 | +10.31 | +15.96 | −6.0 to +37.9 | 0.13 | 0.05 |
| Item 1A (Risk Factors) only, firm-relative | FY2018–FY2022 | 15 | 20 | −9.85 | +1.83 | +11.68 | −32.0 to +55.4 | 0.50 | 0.35 |
| Item 7 (MD&A) only, firm-relative | FY2018–FY2022 | 15 | 20 | −3.15 | +4.46 | +7.61 | −45.8 to +61.0 | 0.71 | 0.50 |

The headline row and the raw same-years row match `app_data/plot.json`. Firm-relative bins start in FY2018 because a firm needs two earlier scored years; raw bins exist from FY2016, which is why the all-years raw row has more firm-years. CRSP prices end in December 2024, so FY2022 filings (filed early 2023) are the last with a full 12-month window. With 19 firms, B1 holds three firms a year and the other bins four.

**How to read this.** No specification is significant at 5% on the yearly basket test (the smallest p is 0.13, Jaccard raw). Only the descriptive Welch test on Jaccard raw reaches p = 0.05, and that test overstates precision. All nine point the predicted way (B5 > B1). The two largest spreads, Jaccard raw and `relative_min_history: 3`, are alternatives, not the headline. We keep the headline as fixed in `config.yaml` before these alternatives were run; picking the best-looking row after the fact would be specification search. With five yearly observations per test, none of this is evidence either way.

**Reproduce:** run `make all` once (it writes `data/`), then

```bash
PYTHONPATH=src .venv/bin/python scripts/specs_tried.py
```

The script reuses the pipeline's own binning (`t4_bins.py`) and statistics (`t6_plot.py`). Prices are the cached CRSP `data/prices_monthly.csv` (latest month December 2024).

## 3. Choices not varied yet

| Choice | Current setting | Planned check |
|---|---|---|
| Firm universe | 20 hand-picked large firms that file through FY2025 | Point-in-time universe, keeping firms that later delist (self-audit #3) |
| Bin cutoffs | Ranked within each fiscal year | Cutoffs from the previous year's scores, so a filing is binned when it is public (self-audit #2) |
| Mean vs median | Means | Medians and trimmed means; on medians B5 − B1 is about +2 pp (self-audit #8) |
| Format breaks | All filings kept | Drop PFE FY2020 and HON FY2020 (self-audit #10) |
| Return window start | End of the filing month | Next month-end when filed on the month's last trading day (self-audit #1) |
| Market adjustment | Excess over SPY (beta = 1) | Beta from the 36 months before each filing (proposal §4) |
| Return window | 12 months | 3-month holds, as in the paper's calendar-time portfolios |

Each will get a row in section 2 when it is run, whatever it shows.
