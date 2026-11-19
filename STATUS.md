# Status

## Checkpoint 1 memo (reconstructed)

*This memo wasn't committed by the Oct 23 deadline. It was written on Nov 17, 2026 from the repo's earliest commits (Nov 6–7) to show where the project started.*

**What we picked and why.** We're replicating *Lazy Prices* (Cohen, Malloy & Nguyen, 2020): firms that heavily rewrite their 10-K tend to underperform afterward. We picked it because every input is free and checkable. The 10-Ks come from SEC EDGAR and prices from CRSP (WRDS). The signal (text similarity to last year's 10-K) is simple enough to rebuild from raw filings and verify by hand.

**What the proof of concept got, and what broke.** Our first version ran end to end on 5 firms (INTC, PFE, JPM, MCD, CAT) over FY2020–2025:

- It downloaded the 10-Ks, cleaned them, and scored cosine and Jaccard similarity against the prior year.
- It ranked firms into five bins within each year and attached 12-month returns.

Three things broke:

- **Scoring the whole 10-K picked up boilerplate.** We narrowed scoring to Item 1A (Risk Factors) and Item 7 (MD&A). Every firm lays these sections out differently, so we wrote heading rules per layout. PFE puts its MD&A in an exhibit before FY2020.
- **Raw similarity ranked companies, not events.** INTC landed in the most-changed bin almost every year because its 10-K always moves more. We switched to change relative to each firm's own earlier years.
- **Five firms are too few for any statistics.**

**Questions for you.**

1. For the full sample, what's the best source for a point-in-time firm universe, such as historical S&P 500 membership, so we avoid survivorship bias?
2. The paper sets bin cutoffs from an earlier distribution of scores. Is that the prior month or the prior year, and does it matter for us?
3. Should our main test be the paper's calendar-time portfolio regression, or is a simpler year-by-year comparison acceptable?

## Current status (Nov 17, 2026)

- **Built:** the full pipeline (T1–T8) on 19 firms over FY2015–2025, plus the Streamlit dashboard and 43 passing tests.
- **Headline:** least-changed (B5) minus most-changed (B1) is +10.8 pp of 12-month excess return (CRSP), p = 0.62 on the yearly basket test (A3). That's in the predicted direction but not significant.
- **Audits:** self-audit in `audits/01_self_audit.md`. Instructor audit received Nov 14; fixes are in progress. See `audits/03_audit_response.md`.
- **Next:** fix the instructor audit findings (A1: required files; A2: point-in-time universe instead of today's survivors; A3: year-level B5 − B1 test; A4: commit the small intermediate files so T4–T7 rerun without SEC downloads), then the v1 full sample.
