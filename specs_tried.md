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

Pooled B5 − B1 in 12-month excess return over SPY, percentage points. Full return windows only. Welch t-test that treats every firm-year as independent, which makes the confidence intervals too narrow (self-audit #7).

| Specification | Years | B1 n | B5 n | B1 mean | B5 mean | B5 − B1 (pp) | 95% CI | Welch p |
|---|---|---|---|---|---|---|---|---|
| **Headline:** cosine, Item 1A + 7 combined, firm-relative, `relative_min_history: 2` | FY2018–FY2024 | 28 | 28 | −4.57 | +2.15 | **+6.72** | −11.6 to +25.0 | 0.46 |
| Raw similarity bins (`bin_basis: raw`), same years as headline | FY2018–FY2024 | 28 | 28 | −1.21 | +4.17 | +5.38 | −13.8 to +24.5 | 0.58 |
| Raw similarity bins (`bin_basis: raw`), all scored years | FY2016–FY2024 | 36 | 36 | +0.40 | +4.23 | +3.83 | −11.3 to +18.9 | 0.61 |
| Firm-relative, `relative_min_history: 1` | FY2017–FY2024 | 32 | 32 | −4.54 | +2.02 | +6.57 | −9.6 to +22.8 | 0.42 |
| Firm-relative, `relative_min_history: 3` | FY2019–FY2024 | 24 | 24 | −6.03 | +2.19 | +8.22 | −12.9 to +29.3 | 0.43 |
| Jaccard instead of cosine, firm-relative | FY2018–FY2024 | 28 | 28 | −6.80 | −3.55 | +3.25 | −8.6 to +15.1 | 0.58 |
| Jaccard instead of cosine, raw | FY2016–FY2024 | 36 | 36 | −1.66 | +10.30 | +11.96 | −4.3 to +28.2 | 0.15 |
| Item 1A (Risk Factors) only, firm-relative | FY2018–FY2024 | 28 | 28 | −5.17 | +11.46 | +16.63 | −6.5 to +39.8 | 0.15 |
| Item 7 (MD&A) only, firm-relative | FY2018–FY2024 | 28 | 28 | +1.75 | −1.16 | −2.90 | −22.5 to +16.7 | 0.77 |

The headline row and the raw same-years row match `app_data/plot.json`. Firm-relative bins start in FY2018 because a firm needs two earlier scored years; raw bins exist from FY2016, which is why the all-years raw row has more firm-years.

**How to read this.** No specification is significant at 5%. Eight of nine point the predicted way (B5 > B1); only Item 7 alone does not. The two largest spreads, Item 1A only and Jaccard raw, are alternatives, not the headline. We keep the headline as fixed in `config.yaml` before these alternatives were run; picking the best-looking row after the fact would be specification search. Item 1A alone being stronger and Item 7 alone pointing the other way fits the paper, whose strongest results are in Risk Factors, but with 28 firm-years per bin it is not evidence.

**Reproduce:** run `make all` once (it writes `data/`), then

```bash
PYTHONPATH=src .venv/bin/python scripts/specs_tried.py
```

The script reuses the pipeline's own binning (`t4_bins.py`) and statistics (`t6_plot.py`). Prices are the cached `data/prices_monthly.csv` (latest full window ends 2026-10-30).

## 3. Choices not varied yet

| Choice | Current setting | Planned check |
|---|---|---|
| Firm universe | 20 hand-picked large firms that file through FY2025 | Point-in-time universe, keeping firms that later delist (self-audit #3) |
| Bin cutoffs | Ranked within each fiscal year | Cutoffs from the previous year's scores, so a filing is binned when it is public (self-audit #2) |
| Significance test | Pooled Welch t-test on firm-years | t-test on the yearly B5 − B1 basket differences, or clustering by year (self-audit #7) |
| Mean vs median | Means | Medians and trimmed means; on medians B5 − B1 is about +2 pp (self-audit #8) |
| Format breaks | All filings kept | Drop PFE FY2020 and HON FY2020 (self-audit #10) |
| Return window start | End of the filing month | Next month-end when filed on the month's last trading day (self-audit #1) |
| Market adjustment | Excess over SPY (beta = 1) | Beta from the 36 months before each filing (proposal §4) |
| Return window | 12 months | 3-month holds, as in the paper's calendar-time portfolios |

Each will get a row in section 2 when it is run, whatever it shows.
