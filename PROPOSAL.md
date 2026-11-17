# Proposal: Lazy Prices on a 20-firm pilot

## 1. The question

Do firms who make significant changes to their Risk and MD\&A sections of their 10-Ks underperform in the market? The individuals most likely to pay for the answer would include hedge funds and other asset managers. This is because they are always looking for a supposed edge on the market, and this project would be able to provide an advantage based solely off of SEC material. 

## 2. The data

The unit of observation is a firm-fiscal-year: one original 10-K, compared with the same firm’s 10-K from the year before and joined to the stock’s return over the 12 months after the filing. Each row identifies the firm by ticker, company name, SEC number and sector, and gives the fiscal year, the prior fiscal year it’s compared to and the date from which the filing came from. For the signal, it has the cosine similarity for the Risk Factors and Management’s Discussion and Analysis sections combined and for each one separately, with Jaccard similarity as a robustness check. It also has the change score calculated as one minus similarity, the firm’s median change in earlier years, the relative change and the quintile bin for the year, where bin 1 is the most changed. For the outcome, it has the window start and end dates, the firm’s 12-month return, the S\&P 500’s return over the same window, the excess return and an indication if the current year is not finished.

**Sample Rows:**

![][image1]

![][image2]

![][image3]

| Raw input | Source | How you get it | Where it lives in the repo |
| :---- | :---- | :---- | :---- |
| ticker | Hand-entered by the team | Typed into the config (20 firms) | config.yaml, firms: (ticker:) |
| name | Hand-entered by the team | Typed into the config | config.yaml (name:) |
| sector | Hand-entered by the team | Typed into the config | config.yaml (sector:) |
| fy | SEC 10-K filing header (period of report) | Parsed from each downloaded 10-K in step 1 (make download) | data/filings\_manifest.csv, code in src/pilot/t1\_download.py |
| filing\_date | SEC 10-K filing header and EDGAR submissions JSON | Parsed from each downloaded 10-K in step 1 | data/filings\_manifest.csv, code in src/pilot/t1\_download.py |
| 10-K full text, behind cosine\_sim, jaccard\_sim, cosine\_risk\_factors and cosine\_mdna | SEC EDGAR | sec-edgar-downloader fetches form 10-K by CIK in step 1 | data/raw/sec-edgar-filings/{cik}/10-K/{accession}/full-submission.txt |
| Monthly adjusted prices (adj\_close), behind firm\_return\_pct, spy\_return\_pct and excess\_return\_pct. SPY is the S\&P 500 benchmark. | Yahoo Finance | yfinance downloads daily adjusted closes by ticker and converts them to month-end in step 5 (make returns) | data/prices\_monthly.csv, code in src/pilot/t5\_returns.py, benchmark set in config.yaml (benchmark\_ticker: SPY) |

## 3. The method

The pipeline runs in eight steps that match the files in src/pilot/, and makes them all run in order. t1\_download.py pulls every original 10-K for fiscal years 2015 to 2025 from SEC EDGAR and records each filing’s company, period and filing date. T2\_clean.py and t2\_sections.py strip each filing down to plain text and cut out Item 1A (Risk Factors) and Item 7 (Management’s Discussion and Analysis). T3\_score.py computes the cosine similarity of word counts between each year’s sections and the prior year’s. T4\_bins.py turns that into a change score and divides it by the firm’s median change in earlier years to get relative change, and ranks firms within each year into 5 quintiles. T5\_returns.py uses monthly adjusted prices from Yahoo Finance to measure each firm’s yearly return starting at the end of the filing month, minus the S\&P 500’s return over the same time period. T6\_plot.py draws the firm, pooled, heatmap and basket graphs, and t7\_coverage.py reports every gap in the data. T8\_diff.py shows the actual sentences that were added and removed between two years.

## 4. Threats and checks

We noticed a few threats with how we calculate relative change as well as the years for which we picked. The benchmark overlaps the sample and the excess return assumes every stock moves completely with the market. All of the we have selected thus far are in the S\&P 500, and subtracting the index’s return treats every firm as having a beta of 1\. The means that firms like Coca-Cola and other low beta firms will appear to do poorly in strong years without anything going wrong. If steady, low-beta firms tend to land in bin 5 and volatile firms in bin 1\. To check this, we’ll estimate each firm’s beta from the 36 months before each filing and rerun the bin comparison on the firm's beta adjusted returns. Not necessarily a threat, but something interesting to note is that in 2020, the SEC released regulations S-K which forced most firms to rewrite their risk sections of their 10-K. Ranking within each year cancels the shared part of the shock, but the 2020 change then is present in every firm’s baseline for 2021 onward. Another threat that we had to address was that the relative change divides a firm’s change this year by its usual change. For firms whose 10-Ks barely change from year to year, both numbers are close to zero. Dividing a few small edits in one year by another lets a few edited sentences produce a large ratio, so a firm can land in bin 1 even though it barely rewrote anything. To check this, we’ll set a minimum on the usual change and see whether the same firms stay in bin 1 when we bin on just the similarity.

## 5. Dashboard mockup

The live dashboard: https://team-backrow-final-project-ghs5gtuwudvjks7fkjquxn.streamlit.app/

![][image4]

![][image5]

[image1]: proposal/images/image1.png

[image2]: proposal/images/image2.png

[image3]: proposal/images/image3.png

[image4]: proposal/images/image4.png

[image5]: proposal/images/image5.png