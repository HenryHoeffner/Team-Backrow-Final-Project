# Lazy Prices Pilot: One Graph per Firm

**Status:** built. T0–T8 are implemented and every check passes. Run `make setup` once, set `SEC_USER_NAME` / `SEC_USER_EMAIL`, then `make all` (about 4 minutes, about 2.7 GB of filings). Prices are cached in `data/prices_monthly.csv`; use `python -m pilot returns --refresh` to pull new ones. `make diffs` writes the T8 sentence diffs for the three lowest-similarity filings.

## How to run (in order)

Each step reads the files the step before it wrote, so run them top to bottom. `make all` runs steps 1–7 in this order for you. Code lives in `src/pilot/`, and the file prefix (`t1_`, `t2_`, …) is the run order.

| Step | Command | Code | Reads | Writes |
| --- | --- | --- | --- | --- |
| 0 | `make setup` (once) | – | `pyproject.toml` | `.venv/` |
| 1 | `make download` | `t1_download.py` | `config.yaml`, SEC EDGAR | `data/raw/`, `data/filings_manifest.csv` |
| 2 | `make clean` | `t2_clean.py`, `t2_sections.py` | filings manifest, raw filings | `data/clean/*.txt` (whole 10-K), `data/sections/*.txt` (Item 1A and Item 7) |
| 3 | `make score` (part 1) | `t3_score.py` | section text | `data/similarity.parquet` |
| 4 | `make score` (part 2) | `t4_bins.py` | similarity table | adds `rel_change`, `bin_relative`, `bin_raw` and `bin` to `data/similarity.parquet` |
| 5 | `make returns` | `t5_returns.py` | similarity table, prices (Yahoo or cache) | `data/prices_monthly.csv`, `data/returns.parquet` |
| 6 | `make plot` | `t6_plot.py` | similarity + returns | `outputs/figures/*.png` (5 firms + `pooled_by_bin.png`), `data/pooled_by_bin.csv` |
| 7 | `make coverage` | `t7_coverage.py` | step reports in `data/reports/` | `outputs/coverage.txt` |
| 8 | `make diffs` (optional) | `t8_diff.py` | section text, similarity table | `outputs/diffs/*.html` |

`make test` runs the unit tests (`tests/test_t*_*.py`, named after the step they test) at any point. Shared code: `cli.py` (the `python -m pilot <step>` entry point) and `config.py` (paths and `config.yaml` loading).

## Goal

Produce one graph for each of five firms. Each graph shows how the firm's stock returned in the year after each 10-K filing, and colors each year by **how much the firm's 10-K changed compared with the year before**. The graph is a visual check of the Lazy Prices idea (Cohen, Malloy & Nguyen, *Journal of Finance*, 2020): companies that rewrite their annual report heavily tend to earn lower returns afterward than companies that barely change it.

The pilot exists to prove the pipeline end to end: download filings, clean them, score the change, rank, attach returns, plot. It cannot show whether the effect is real. Five firms are far too few for that.

### The graph (deliverable)

One PNG per firm: `outputs/figures/{TICKER}_yearly_returns.png`, plus one pooled PNG, `outputs/figures/pooled_by_bin.png` (see **The pooled graph** below).

The table describes the default `plot_return: excess`. With `plot_return: raw` the graph keeps the original look: title `{TICKER}: Yearly Return After 10-K Filing`, y axis in percent, and the S&P 500 return drawn as its own gray line.

| Element | Specification |
| --- | --- |
| Title | `{TICKER}: Return vs S&P 500 in the Year After 10-K Filing` |
| X axis | Filing year (integer ticks, one per year) |
| Y axis | Excess return: the firm's 12-month return minus the S&P 500's over the same window, in percentage points (`+20 pp`) |
| Gray line | The S&P 500 (SPY adjusted close) as a flat line at 0, since every point is already measured against it |
| Firm line | The firm's 12-month excess return after each filing. Only filings with a bin are plotted. Each line segment takes the color of the bin at its later end point. Each point has a round marker in its own bin color, with a thin dark outline and a small text label (`Q1` to `Q5`) so the bin does not depend on color alone |
| Colors | Q1 red `#e41a1c` (largest change), Q2 orange `#ff9900`, Q3 yellow `#f2d600`, Q4 lime `#a6e22e`, Q5 dark green `#1a9e1a` (smallest change), S&P gray `#b0b0b0` |
| Legend | Below the plot: the five bins with "Q1 = largest change in 10-K" and "Q5 = smallest change", plus the gray `S&P 500 (= 0)` entry |
| Partial window | If a 12-month window runs past the latest available price month, plot it with a hollow marker and annotate `through <Mon YYYY>` |
| Footnote | Small text, two lines: `Bins rank the 5 pilot firms within each year on how much Risk Factors (Item 1A) + MD&A (Item 7) changed vs the prior-year 10-K, relative to the firm's own median change in earlier years. FY2015 is the comparison base and FY2016-FY2017 build each firm's history, so they are not plotted.` |
| Size | 8 x 4.5 inches at 200 dpi |

Each firm has eleven 10-Ks (FY2015–FY2025): FY2015 is the comparison base, FY2016–FY2017 build the firm's history for the firm-relative score, so each graph has eight points (FY2018–FY2025). The target look is a gray market line with the firm's line on top, colored by bin.

### The pooled graph

`outputs/figures/pooled_by_bin.png`, 8 x 4.5 inches at 200 dpi. Two panels with a shared y axis. Both use the same firm-years: every filing with a firm-relative bin and a full 12-month window (FY2018–FY2024, n = 35). Left panel: bins on the firm-relative change score. Right panel: bins on raw cosine similarity, for comparison. Within each panel, one dot per firm-year in its bin color; each bin's mean as a dark bar with a 95% t confidence interval; the S&P 500 as a gray line at 0; and in the corner `Q5 − Q1` (mean difference, Welch 95% CI, p-value). The Lazy Prices prediction is Q5 − Q1 > 0. The footnote says that filings are treated as independent and that the sample is far too small to test the effect. Bin means are written to `data/pooled_by_bin.csv`.

## Scope and decisions

Five hand-picked firms, one per sector. CIKs were checked against SEC filing pages. All have December fiscal year ends, so the fiscal-year label is simply the calendar year of the period end.

| Ticker | Company | CIK | Sector |
| --- | --- | --- | --- |
| INTC | Intel Corp | 0000050863 | Information Technology |
| PFE | Pfizer Inc | 0000078003 | Health Care |
| JPM | JPMorgan Chase & Co | 0000019617 | Financials |
| MCD | McDonald's Corp | 0000063908 | Consumer Discretionary |
| CAT | Caterpillar Inc | 0000018230 | Industrials |

- **Filings:** original 10-Ks for fiscal years 2015–2025 (FY2015 is only the comparison base). Drop 10-K/A amendments. Flag 10-KT transition reports and exclude them from pairing.
- **Signal:** cosine similarity between a 10-K and the same firm's previous 10-K, on **Item 1A (Risk Factors) and Item 7 (MD&A) only**, scored together. Each section's own cosine is saved as well (`cosine_risk_factors`, `cosine_mdna`). Jaccard similarity is computed too, as a robustness column, but the graph uses cosine.
- **Returns:** free monthly adjusted prices (try `yfinance`) for the five tickers and SPY.
- **Why these firms:** self-contained 10-Ks and December year ends. IBM was dropped because its 10-K puts the MD&A and financials in a separate exhibit. Not a random sample, so results say nothing about the typical company.

```yaml
# config.yaml
firms:
  - {ticker: INTC, cik: "0000050863", name: "Intel Corp",          sector: "Information Technology"}
  - {ticker: PFE,  cik: "0000078003", name: "Pfizer Inc",          sector: "Health Care"}
  - {ticker: JPM,  cik: "0000019617", name: "JPMorgan Chase & Co", sector: "Financials"}
  - {ticker: MCD,  cik: "0000063908", name: "McDonald's Corp",     sector: "Consumer Discretionary"}
  - {ticker: CAT,  cik: "0000018230", name: "Caterpillar Inc",     sector: "Industrials"}
fiscal_years: [2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
sections: [risk_factors, mdna]   # Item 1A Risk Factors, Item 7 MD&A; scored together
bin_measure: cosine
bin_basis: firm_relative     # firm_relative: change vs the firm's own earlier years; raw: plain similarity
relative_min_history: 2      # earlier scored years a firm needs before it gets a firm-relative bin
plot_return: excess          # excess: firm minus S&P 500; raw: firm and S&P 500 as separate lines
return_window_months: 12
benchmark_ticker: SPY
```

Keep `fiscal_years` configurable. Extending the window backward later should be a one-line change.

## Definitions (use exactly these)

**Fiscal year (FY).** The calendar year of the filing header's period-of-report date.

**Similarity.** Cosine similarity of word-count vectors of the cleaned text of Item 1A and Item 7 combined, for the 10-K of year FY and the 10-K of FY-1. Range 0 to 1. Lower means more change.

**Sections.** Item 1A and Item 7 are cut out of the cleaned 10-K by their headings (`t2_sections.py`). Firms lay out the 10-K differently: CAT and PFE use standard Item headings; JPM uses one for Item 1A and an MD&A page header for Item 7; INTC and MCD use their own order and give Item numbers only in a cross-reference index. A heading that carries its Item number runs to the next Item heading; a plain-name heading ("Risk factors") runs to the next section name. The table of contents is skipped because its entries are a line apart. A span under 1,000 words is a pointer, not the section. When Item 7 in the 10-K is only a pointer, the MD&A is taken from the EX-13 annual-report exhibit (PFE FY2015–2019, its "Financial Review"). A filing missing either section is not scored, and the gap is recorded.

**Change and firm-relative change.** `change = 1 − cosine similarity`. A firm's `prior_median_change` for year FY is the median `change` over its scored years before FY; only earlier years are used, so the score never uses future data. `rel_change = change / prior_median_change`: 2.0 means the firm changed its 10-K twice as much as usual. It is blank until the firm has `relative_min_history` (default 2) earlier scored years. Why: with raw similarity, a firm whose 10-K always moves more (INTC) sits in Q1 almost every year, so the bins rank companies, not events. On the pilot data INTC is Q1 in 6 of 10 years on raw similarity and 1 of 8 on firm-relative change.

**Bin.** For each fiscal year, rank the firms by `rel_change` from highest to lowest (`bin_basis: firm_relative`, the default), or by cosine similarity from lowest to highest (`bin_basis: raw`); either way rank 1 is the most changed. Both are saved, as `bin_relative` and `bin_raw`; `bin` is the one `bin_basis` picks. Years where no firm has a firm-relative score get no bin. With `n` firms scored that year, `bin = ceil(5 * rank / n)`. With all five firms present, the bin equals the rank. Ties break alphabetically by ticker and are logged. **Bin 1 is always the most changed and Bin 5 the least changed.** Never flip this.

**Return window.** Let `m0` be the last trading day of the month in which the 10-K was filed (the filing date comes from the header). Start price is the adjusted close at `m0`. End price is the adjusted close 12 month-ends later. Return = end / start - 1, in percent. This starts the clock after the filing is public, so there is no lookahead. If the end month is later than the latest available price, use the latest available month and set `partial = True`.

**S&P 500 comparison.** The same window applied to SPY adjusted close, one value per firm-filing so it lines up with the firm's window.

**Excess return.** `excess_return_pct = firm_return_pct − spy_return_pct`, in percentage points: market-adjusted, with no beta adjustment. The graphs and the pooled comparison use it, because the Lazy Prices claim is about returns relative to the market, not raw returns.

**X position.** The filing year, from the filing date.

## Build plan for Claude Code

Do the tasks in order. After each task, run its check. Do not start the next task until the check passes. If a check cannot pass because of the data (for example a missing filing), record the reason in `outputs/coverage.txt` and continue only if the gap does not break the next step.

**T0. Scaffold.** Create `pyproject.toml` (Python 3.11 or newer), `config.yaml`, `.gitignore` (ignore `data/` and `outputs/`), a `src/pilot/` package, `tests/`, and a `Makefile` with targets `download`, `clean`, `score`, `returns`, `plot`, `all`, `test`.
*Check:* `make test` runs; `python -m pilot --help` works.

**T1. Download.** Use `sec-edgar-downloader`. Read the installed version's `get()` signature before calling it, since argument names changed across versions. Use the CIK as the identifier, fetch `10-K` filings filed after `2021-01-01` with `download_details=True`, and throttle to well under 10 requests per second with retries. Skip anything already on disk. Do not assume the folder layout; discover it. Parse the SEC header in each `full-submission.txt` for company name, submission type, period of report and filing date. Write `data/filings_manifest.csv` with columns `ticker, cik, accession, form, period_of_report, filing_date, fy, path`. Keep periods ending 2020–2025 only.
*Check:* up to 55 rows, 11 per firm, all `form = 10-K`; each header company name matches `config.yaml`. Missing FY2025 filings (filed in early 2026) are reported. If any firm lacks FY2025, drop FY2025 for every firm and say so.

**T2. Clean.** From each filing, take only the document of type `10-K`, not the exhibits or graphics that sit in the same file. For inline-XBRL HTML, remove the hidden `ix:header` block and other hidden elements before extracting text. Remove tables that are more than 15% numeric (the original paper's rule), strip tags, lowercase, normalize whitespace. Write `data/clean/{cik}_{fy}.txt` and log word counts. Then cut out Item 1A and Item 7 (see **Sections**) to `data/sections/{cik}_{fy}_{risk_factors|mdna}.txt`.
*Check:* every filing has a clean file; flag any word count above 3 times or below one third of that firm's median; open three random clean files and confirm they read as normal prose with no leftover markup.

**T3. Score.** For each firm and FY from 2016, compare the Item 1A + Item 7 text to FY-1. Write `data/similarity.parquet` with columns `ticker, cik, fy, prev_fy, filing_date, cosine_sim, jaccard_sim, n_words, n_words_prev`, plus `cosine_<section>` and `n_words_<section>` for each section.
*Check:* 50 rows; scores between 0 and 1; a filing compared with itself scores 1 (unit test). Print the three lowest-similarity rows for manual review.

**T4. Bin.** Add `change`, `prior_median_change`, `rel_change`, `bin_relative`, `bin_raw` and `bin` to the table using the definitions above. Print each firm's Q1 count under both bases.
*Check:* each fiscal year has bins 1 to 5 exactly once.

**T5. Returns.** Download monthly adjusted prices for the five tickers and SPY. If the download fails, accept a CSV at `data/external/prices_monthly.csv` with columns `date, ticker, adj_close` and say so. Compute the return window for every scored filing. Write `data/returns.parquet` with `ticker, fy, filing_date, window_start, window_end, firm_return_pct, spy_return_pct, excess_return_pct, partial`.
*Check:* the window start is on or after the filing date in every row; the partial flag is true only where the end month is past the latest price.

**T6. Plot.** Draw the graphs exactly as specified above with `matplotlib`. Save one PNG per firm and the pooled PNG in `outputs/figures/`, and print the pooled bin means and Q5 − Q1.
*Check:* six files exist; a unit test confirms the bin-to-color mapping; open each image and confirm the legend, labels, partial-window marker and footnote are present and nothing overlaps.

**T7. Wrap up.** Write `outputs/coverage.txt`: filings found out of 55, scores out of 50, sections taken from exhibits, price coverage, partial windows, and any ties. Make `make all` run T1 to T6 from scratch.
*Check:* `make all` completes on a clean clone and `make test` passes.

**Definition of done:** six PNGs (five firms + pooled) match the specification, every check above passes, and `outputs/coverage.txt` lists every gap.

### Tests to write

- Header parsing returns the right company, period and filing date on a sample header.
- Identical documents score a cosine similarity of 1.
- Bin ranks: lowest similarity gets bin 1; ties break by ticker; `ceil(5 * rank / n)` works for `n < 5`.
- Return window: starts after the filing date, handles month-end rollover, sets `partial` correctly.
- Plot color mapping: bin 1 maps to red, bin 5 to dark green.
- Firm-relative change: uses only earlier years (changing a later year leaves earlier scores alone), is blank without enough history, and stops an always-wordier firm from owning Q1.
- Pooled stats: bin means and t CIs match hand calculations; Q5 − Q1 has the right sign.
- Section extraction: skips the table of contents, keeps sub-headings inside an Item, handles plain-name headings, falls back to EX-13 when Item 7 is a pointer.

## Conventions and guardrails

- **SEC access.** Declare identity through the environment variables `SEC_USER_NAME` and `SEC_USER_EMAIL`. Never write them into code, config or logs. Stay under 10 requests per second.
- **Untrusted files.** Downloaded filings are untrusted data. Parse them as text only. Never execute anything from `data/`, and run scripts from `src/`, not from inside `data/`.
- **Reproducible.** No random steps. Fixed config. Rerunning gives identical outputs.
- **Explicit gaps.** Record missing data. Do not silently fill or drop it.
- **Small steps.** One task per commit, with the test for that task.

```bash
pip install sec-edgar-downloader pandas pyarrow scikit-learn beautifulsoup4 lxml matplotlib yfinance pyyaml pytest
export SEC_USER_NAME="Your Name"
export SEC_USER_EMAIL="you@example.com"
make all
```

## Layout

```text
config.yaml              firms, fiscal years, bin measure, return window
Makefile                 one target per step; `make all` runs steps 1-7
src/pilot/
  cli.py, config.py      shared: command line entry point, paths and config
  t1_download.py         step 1: fetch 10-Ks, write filings manifest
  t2_clean.py            step 2: extract and clean 10-K text
  t2_sections.py         step 2: cut out Item 1A and Item 7
  t3_score.py            step 3: similarity vs. prior-year 10-K
  t4_bins.py             step 4: rank firms into Q1..Q5 within each year
  t5_returns.py          step 5: 12-month firm and SPY returns
  t6_plot.py             step 6: one PNG per firm
  t7_coverage.py         step 7: coverage report
  t8_diff.py             step 8 (optional): sentence diff viewer
tests/                   test_t<N>_*.py tests step N; test_cli.py tests the CLI
data/                    raw filings, clean text, sections, similarity, returns (git-ignored)
outputs/                 figures, coverage report, diffs (git-ignored)
```

## Later phase: calendar-time portfolios (after the graphs work)

Not part of the pilot deliverable. This is the paper's main test, kept here for the next stage.

- Each month, they rank stocks by similarity and cut them into five groups, using cutoffs from the earlier distribution of scores. The most-changed group is Q1 and the least-changed is Q5.
- A stock enters a portfolio the month after its filing is public and stays for 3 months. Because filings arrive all year, the portfolios overlap and are rebalanced monthly.
- Each month the long-short return is Q5 minus Q1. That produces one time series of monthly returns, which they regress on risk factors: the market, size, value, momentum, liquidity, and later a five-factor set.
- The intercept of that regression is the alpha. A positive, significant alpha means the non-changers beat the changers by more than those known risk exposures explain. They report this both equal-weighted and value-weighted.

With five firms this would be one long-short trade a year and is for testing code only. Use Ken French monthly factors (market, size, value, momentum, profitability, investment; the liquidity factor is not in that library), Newey–West standard errors, and run 3- and 12-month holds.

## Reference project and proposed changes

The main idea matches a public replication, a Streamlit app at `lazypricesreplication.streamlit.app`. We reuse none of its code or text; the graph above follows its general look (market line in gray, firm line colored by bin), and we credit it. That project covers S&P 500 firms from 1993 to 2024, uses Loughran–McDonald 10-K word-count files instead of downloading filings, and compares annual returns across five similarity bins. It labels bins in opposite directions in its method text and its chart legend, shows no significance test on the pages we have, and does not say whether its S&P 500 list is as of each date.

This project differs by using raw filings from EDGAR (so word order and sections are available), a recent window, and, in the full project, a comparison with other published predictors (Open Asset Pricing).

| # | Proposed change | Why | In this README |
| --- | --- | --- | --- |
| 1 | One bin convention, Q1 most changed | Avoids the reference's label confusion | Yes |
| 2 | Monthly returns with factor alphas and t-statistics | Raw averages cannot separate the signal from market exposure | Later phase |
| 3 | Compare post-2014 returns with in-sample and with other published predictors | The question the reference does not ask | Full project |
| 4 | Rank within each year before binning | Cosine scores sit very close to 1 | Yes (bin definition) |
| 5 | Report uncertainty and word conclusions to match | Avoid claiming support without a test | Partly (pooled graph shows 95% CIs and Q5 − Q1 p-value; factor test is later) |
| 4b | Rank change relative to each firm's own history | Raw similarity mostly ranks firms by writing style | Yes (`bin_basis: firm_relative`) |
| 4c | Use returns in excess of the S&P 500 | Raw returns mix in the market | Yes (`excess_return_pct`, `plot_return: excess`) |
| 6 | Point-in-time firm universe | Avoid survivorship bias | Full project |
| 7 | "What changed" viewer: sentences added and removed between two years | Lets a person check a low score by eye | Stretch, task T8 below |
| 8 | Section-level similarity for Risk Factors (Item 1A) | The paper's strongest results come from that section | Yes (Item 1A + Item 7 scored; per-section columns saved) |
| 9 | Sentiment, uncertainty and length controls | Tests whether tone explains the result | Stretch |
| 10 | Small Streamlit app | Easier to post and explore | Stretch |

**T8 (stretch): diff viewer.** For a chosen firm and year, write an HTML file listing sentences added and removed between the two cleaned 10-Ks, using `difflib`. Save to `outputs/diffs/{TICKER}_{FY}.html`. Use it to review the three lowest-similarity rows from T3.

## Known limitations

- **Tiny sample.** 50 scored filings. The graphs illustrate the method and prove the pipeline; they are not evidence about the effect.
- **Eight points per graph.** One annual return per binned filing; FY2016–FY2017 only build each firm's history.
- **Format breaks persist in the firm-relative score.** PFE's FY2020 move of its MD&A into the 10-K makes FY2020–FY2022 look large next to its calm pre-2020 baseline, so PFE is Q1 in 4 of 8 years. A shorter rolling baseline would adapt faster but is noisier with this little history.
- **Excess return is market-adjusted only.** No beta or factor adjustment; that is the calendar-time portfolio test in the later phase.
- **Last window may be partial.** FY2025 filings are entered around March 2026, so their 12-month window runs past the latest prices.
- **Hand-picked firms.** Large, stable companies chosen for clean data.
- **10-K only.** The original paper also used 10-Qs.
- **Free data.** Survivorship bias and missing delisting returns matter less for five large, still-listed firms.
- **Text coverage.** Only Item 1A and Item 7 are scored. Business, legal proceedings, financial-statement notes and everything in the proxy statement are not in the signal.
- **Format breaks.** PFE moved its MD&A from the EX-13 "Financial Review" (about 45,000 words, including a glossary) into Item 7 (about 15,000 words) in FY2020, so PFE FY2020 vs FY2019 partly measures that move. The coverage report lists these years.
- **Heading rules are per layout.** Section boundaries were checked by hand for these five firms. A new firm may need a new heading pattern in `t2_sections.py`; a missing section shows up as a gap, not a silent fallback.
- **Quintile cutoffs.** The paper sets them from an earlier distribution of scores; sources I read disagree on whether that is the prior month or the prior year. The pilot ranks firms within each year. Confirm against the paper's PDF before the full project.

## References

- Cohen, Malloy & Nguyen (2020), [Lazy Prices](https://www.nber.org/papers/w25084), *Journal of Finance* 75(3).
- [sec-edgar-downloader documentation](https://sec-edgar-downloader.readthedocs.io/)
- [SEC: Accessing EDGAR Data](https://www.sec.gov/edgar/searchedgar/accessing-edgar-data.htm)
- Reference project: public Streamlit replication of Lazy Prices (`lazypricesreplication.streamlit.app`).
- Chen & Zimmermann, [Open Source Cross-Sectional Asset Pricing](https://www.federalreserve.gov/econres/feds/open-source-cross-sectional-asset-pricing.htm) (full project).
