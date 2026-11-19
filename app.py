"""Lazy Prices dashboard.  Run the pipeline first (make all), then:  make app

Every number here is computed from data/similarity.parquet and data/returns.parquet with
the pipeline's own functions (src/pilot/dashboard.py), so it matches outputs/.
"""
import math
import sys
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from pilot.config import load_config  # noqa: E402
from pilot.dashboard import (  # noqa: E402
    BASES, BIN_WORDS, SNAPSHOT_TABLE, baskets, coverage_text, diff_files, load, pooled, snapshot_dir,
)
from pilot.style import BIN_COLORS  # noqa: E402

st.set_page_config(page_title="Lazy Prices, revisited", layout="wide")

BIN_LABELS = [f"B{b}" for b in range(1, 6)]
BIN_SCALE = alt.Scale(domain=BIN_LABELS, range=[BIN_COLORS[b] for b in range(1, 6)])
REPO_URL = "https://github.com/HenryHoeffner/Team-Backrow-Final-Project"


def signed(v: float, digits: int = 1) -> str:
    """+6.7 / −4.6 with a true minus sign."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "n/a"
    s = f"{v:+.{digits}f}"
    return s.replace("-", "−")


# --------------------------------------------------------------------------- data

@st.cache_data
def load_data(mtimes: tuple) -> tuple[pd.DataFrame, str]:
    """mtimes is only the cache key: rerunning the pipeline or a new snapshot reloads the data."""
    return load(load_config())


cfg = load_config()
# On a computer that ran the pipeline the app reads data/; the hosted site reads app_data/.
sources = [cfg.paths.similarity, cfg.paths.returns, snapshot_dir(cfg) / SNAPSHOT_TABLE]
try:
    df, source = load_data(tuple(p.stat().st_mtime if p.exists() else 0 for p in sources))
except FileNotFoundError:
    st.error("No results found. Run `make all` first, then `make app`.")
    st.stop()
df["bin_label"] = "B" + df["bin_relative"].astype(str)
latest_price = df["window_end"].max()

# --------------------------------------------------------------------------- header

st.title("Lazy Prices, revisited")
st.caption("Team Backrow · FIN 331 final project · "
           f"prices through {latest_price:%b %Y} · [GitHub repo]({REPO_URL})"
           + (" · data: committed snapshot (app_data/)" if source == "snapshot" else ""))

basis = st.radio("Rank bins by", list(BASES), format_func=BASES.get, horizontal=True,
                 help="The project's main measure compares each firm with its own earlier years. "
                      "Raw similarity is shown for comparison.")
bin_col = basis
summary, spread = pooled(df, bin_col)
full = df[~df["partial"]]

tab_intro, tab_method, tab_results, tab_explore = st.tabs(
    ["Overview", "Methodology", "Results", "Explore a firm"])

# --------------------------------------------------------------------------- overview

with tab_intro:
    st.header("When a company rewrites its annual report, does its stock fall behind?")
    st.markdown(
        "Most companies copy last year's 10-K and change the numbers. "
        "Cohen, Malloy and Nguyen (2020) found that firms which rewrite a lot tend to "
        "underperform afterward, because investors don't read closely. We rebuild that test "
        "from raw SEC filings and ask whether it still shows up in recent years.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Firms", df["ticker"].nunique(), help="Hand-picked large firms, 10 sectors")
    c2.metric("Filings ranked into bins", len(df), f"{len(full)} with a full 12-month window",
              delta_color="off")
    c3.metric("B5 − B1 (least minus most changed)", f"{signed(spread['diff'])} pp a year",
              f"p = {spread['p']:.2f}", delta_color="off")
    st.info("**How to read it.** Each year every firm's 10-K is scored on how much its Risk Factors "
            "and MD&A changed, then firms are split into five bins: **B1 changed the most, B5 the "
            "least**. We then compare each stock with the S&P 500 over the next 12 months. "
            "If Lazy Prices holds, B5 beats B1.")
    st.warning(f"**Bottom line so far:** B5 beat B1 by {signed(spread['diff'])} pp a year, the direction "
               f"the paper predicts, but the 95% range runs from {signed(spread['ci_low'])} to "
               f"{signed(spread['ci_high'])} pp (p = {spread['p']:.2f}). With 20 firms this could easily "
               "be chance.")

# --------------------------------------------------------------------------- methodology

with tab_method:
    st.header("Methodology")
    st.markdown("One command (`make all`) rebuilds every number on this site from the SEC's public "
                "filings and free price data.")
    steps = [
        ("1. Download", "Original 10-Ks for FY2015–FY2025 from SEC EDGAR; amendments dropped."),
        ("2. Clean", "Strip markup and number-heavy tables; cut out Item 1A (Risk Factors) and Item 7 (MD&A)."),
        ("3. Score", "Cosine similarity of word counts versus the same firm's prior-year 10-K."),
        ("4. Bin", "Change relative to the firm's own earlier years, ranked B1–B5 within each year."),
        ("5. Returns", "12 months from the month-end after filing, minus the S&P 500 (CRSP price return plus market dividend yield)."),
        ("6. Compare", "Bin averages with 95% CIs, B5 − B1 with a Welch t-test, yearly baskets."),
    ]
    cols = st.columns(3)
    for i, (title, text) in enumerate(steps):
        with cols[i % 3].container(border=True):
            st.markdown(f"**{title}**")
            st.caption(text)
    left, right = st.columns(2)
    with left:
        st.subheader("Key choices")
        st.markdown(
            "- **Firm-relative change.** Some firms always rewrite a lot. `change = 1 − similarity`, "
            "divided by the firm's median change in its *earlier* years, ranks events instead of "
            "writing styles.\n"
            "- **No look-ahead.** Returns start after the filing is public; a firm's history uses only "
            "earlier years.\n"
            "- **Excess return.** Firm minus the S&P 500 over the same window, in percentage points.\n"
            "- **One convention.** B1 is always the most changed, B5 the least.")
    with right:
        st.subheader("Threats to validity")
        st.markdown(
            "- **Small, hand-picked sample.** 20 large firms that still exist today; results say "
            "nothing about the typical company.\n"
            "- **Format breaks.** PFE moved its MD&A in 2020 and HON redesigned its 10-K; layout "
            "changes score as rewrites.\n"
            "- **Price data ends Dec 2024.** The CRSP monthly file stops there, so later filings have no return window.\n"
            "- **Market-adjusted only.** No beta or factor adjustment yet.\n"
            "- **Open windows.** The latest filings' 12 months aren't over; they're left out of all averages.")
    coverage = coverage_text(cfg)
    if coverage:
        with st.expander("Coverage report (outputs/coverage.txt)"):
            st.code(coverage, language=None)

# --------------------------------------------------------------------------- results

with tab_results:
    st.header("Do bigger rewrites lead to a weaker year?")
    st.caption(f"Return minus the S&P 500 in the 12 months after each filing, by bin "
               f"({BASES[basis].lower()}). Full windows only: {len(full)} filings.")

    pts = full.assign(bin_label="B" + full[bin_col].astype(str))
    # Deterministic sideways spread so dots in a bin don't stack.
    pts["x"] = pts.groupby(bin_col).cumcount()
    pts["x"] = pts[bin_col] + (pts["x"] / pts.groupby(bin_col)["x"].transform("max").clip(lower=1) - 0.5) * 0.5
    summ = summary.assign(bin_label=lambda s: "B" + s["bin"].astype(str), x0=lambda s: s["bin"] - 0.3,
                          x1=lambda s: s["bin"] + 0.3,
                          words=lambda s: s["bin"].map(BIN_WORDS),
                          beat=lambda s: (s["share_beat"] * 100).round().astype(int).astype(str) + "%")
    x_axis = alt.X("x:Q", title=None, scale=alt.Scale(domain=[0.5, 5.5]),
                   axis=alt.Axis(values=[1, 2, 3, 4, 5], labelExpr="'B' + datum.value", grid=False))
    y_axis = alt.Y("excess_return_pct:Q", title="Return minus S&P 500 (pp)")
    band = alt.Chart(summ).mark_rect(opacity=0.18).encode(
        x=alt.X("x0:Q", title=None, scale=alt.Scale(domain=[0.5, 5.5]),
                axis=alt.Axis(values=[1, 2, 3, 4, 5], labelExpr="'B' + datum.value", grid=False)),
        x2="x1", y=alt.Y("ci_low:Q", title="Return minus S&P 500 (pp)"), y2="ci_high:Q",
        color=alt.Color("bin_label:N", scale=BIN_SCALE, legend=None))
    dots = alt.Chart(pts).mark_circle(size=55, opacity=0.8).encode(
        x=x_axis, y=y_axis, color=alt.Color("bin_label:N", scale=BIN_SCALE, legend=None),
        tooltip=[alt.Tooltip("ticker:N", title="Firm"), alt.Tooltip("filing_year:Q", title="Filed"),
                 alt.Tooltip("bin_label:N", title="Bin"),
                 alt.Tooltip("excess_return_pct:Q", title="vs S&P 500 (pp)", format="+.1f")])
    means = alt.Chart(summ).mark_rule(strokeWidth=3, color="#1d1d1b").encode(
        x="x0:Q", x2="x1", y=alt.Y("mean:Q"),
        tooltip=[alt.Tooltip("bin_label:N", title="Bin"), alt.Tooltip("mean:Q", title="Average (pp)", format="+.1f"),
                 alt.Tooltip("ci_low:Q", title="95% CI low", format="+.1f"),
                 alt.Tooltip("ci_high:Q", title="95% CI high", format="+.1f"),
                 alt.Tooltip("n:Q", title="Filings"), alt.Tooltip("beat:N", title="Beat S&P 500")])
    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color="#55534e").encode(y="y:Q")
    st.altair_chart((band + zero + dots + means).properties(height=420), width="stretch")

    m1, m2, m3 = st.columns(3)
    m1.metric("B5 − B1", f"{signed(spread['diff'])} pp")
    m2.metric("95% confidence range", f"{signed(spread['ci_low'])} to {signed(spread['ci_high'])} pp")
    m3.metric("p-value (Welch)", f"{spread['p']:.2f}")
    table = summ[["bin_label", "words", "n", "mean", "ci_low", "ci_high", "beat"]].rename(columns={
        "bin_label": "Bin", "words": "", "n": "Filings", "mean": "Average (pp)", "ci_low": "95% CI low",
        "ci_high": "95% CI high", "beat": "Beat S&P 500"})
    st.dataframe(table, hide_index=True, width="stretch",
                 column_config={c: st.column_config.NumberColumn(format="%+.1f")
                                for c in ("Average (pp)", "95% CI low", "95% CI high")})
    st.caption("Confidence intervals treat filings as independent, so they look more precise than they "
               "are when firms move together in the same year. 20 hand-picked firms: this illustrates "
               "the method; it is not a test of the Lazy Prices effect.")

    st.subheader("Did the most-changed firms lag the least-changed?")
    st.caption("Each year the firms are split into five equal-weighted baskets by bin and held for "
               "12 months. Line = cumulative return ahead of the S&P 500; each point is when that "
               "year's holds end.")
    bk = baskets(df, bin_col).assign(bin_label=lambda b: "B" + b["bin"].astype(str),
                                     extreme=lambda b: b["bin"].isin([1, 5]))
    lines = alt.Chart(bk).mark_line(point=True).encode(
        x=alt.X("window_end:T", title=None),
        y=alt.Y("ahead_pct:Q", title="Ahead of S&P 500 (%)"),
        color=alt.Color("bin_label:N", scale=BIN_SCALE, title="Bin"),
        strokeWidth=alt.StrokeWidth("extreme:N", scale=alt.Scale(domain=[True, False], range=[3.5, 1.6]),
                                    legend=None),
        tooltip=[alt.Tooltip("bin_label:N", title="Bin"), alt.Tooltip("window_end:T", title="As of", format="%b %Y"),
                 alt.Tooltip("ahead_pct:Q", title="Ahead of S&P 500 (%)", format="+.1f"),
                 alt.Tooltip("n:Q", title="Firms that year")])
    st.altair_chart((lines + zero).properties(height=380), width="stretch")
    end = bk.sort_values("window_end").groupby("bin").tail(1).set_index("bin")["ahead_pct"]
    st.caption(f"By {bk['window_end'].max():%b %Y}: "
               + ", ".join(f"B{b} {signed(v, 0)}%" for b, v in end.items())
               + f". B5 − B1: {signed(end[5] - end[1], 0)} points.")

# --------------------------------------------------------------------------- explore

with tab_explore:
    st.header("Explore a firm")
    names = df.drop_duplicates("ticker").set_index("ticker")["name"].to_dict()
    tickers = sorted(names)
    ticker = st.selectbox("Firm", tickers, index=tickers.index("HON") if "HON" in tickers else 0,
                          format_func=lambda t: f"{t} · {names[t]}")
    f = df[df["ticker"] == ticker].copy()
    f["bin_label"] = "B" + f[bin_col].astype(str)
    f["window"] = np.where(f["partial"], "still open", "full 12 months")
    f_full = f[~f["partial"]]
    a, b, c = st.columns(3)
    a.metric("Sector", f["sector"].iloc[0])
    b.metric("Beat the S&P 500", f"{int((f_full['excess_return_pct'] > 0).sum())} of {len(f_full)} full years")
    c.metric("Average vs S&P 500", f"{signed(f_full['excess_return_pct'].mean(), 0)} pp a year")

    bars = alt.Chart(f).mark_bar(size=34).encode(
        x=alt.X("filing_year:O", title="Filing year"),
        y=alt.Y("excess_return_pct:Q", title="Return minus S&P 500 (pp)"),
        color=alt.Color("bin_label:N", scale=BIN_SCALE, title="Bin"),
        opacity=alt.condition("datum.partial", alt.value(0.45), alt.value(1.0)),
        tooltip=[alt.Tooltip("filing_year:O", title="Filed"), alt.Tooltip("bin_label:N", title="Bin"),
                 alt.Tooltip("excess_return_pct:Q", title="vs S&P 500 (pp)", format="+.1f"),
                 alt.Tooltip("firm_return_pct:Q", title="Firm return (%)", format="+.1f"),
                 alt.Tooltip("spy_return_pct:Q", title="S&P 500 return (%)", format="+.1f"),
                 alt.Tooltip("rel_change:Q", title="Change vs usual (x)", format=".2f"),
                 alt.Tooltip("window:N", title="Window")])
    labels = alt.Chart(f).mark_text(dy=-8, fontWeight="bold").encode(
        x="filing_year:O", y="excess_return_pct:Q",
        text=alt.Text("excess_return_pct:Q", format="+.0f"))
    st.altair_chart((bars + labels + zero).properties(height=360), width="stretch")
    st.caption("Faded bar = the 12-month window is still open; it's left out of the averages. "
               "\"Change vs usual\" = this year's change divided by the firm's median change in earlier years.")

    show = f[["filing_year", "bin_label", "rel_change", "cosine_sim", "firm_return_pct",
              "spy_return_pct", "excess_return_pct", "window_start", "window_end", "window"]].rename(columns={
        "filing_year": "Filed", "bin_label": "Bin", "rel_change": "Change vs usual (x)",
        "cosine_sim": "Similarity", "firm_return_pct": "Firm (%)", "spy_return_pct": "S&P 500 (%)",
        "excess_return_pct": "vs S&P 500 (pp)", "window_start": "From", "window_end": "To", "window": "Window"})
    st.dataframe(show, hide_index=True, width="stretch", column_config={
        "Change vs usual (x)": st.column_config.NumberColumn(format="%.2f"),
        "Similarity": st.column_config.NumberColumn(format="%.4f"),
        "Firm (%)": st.column_config.NumberColumn(format="%+.1f"),
        "S&P 500 (%)": st.column_config.NumberColumn(format="%+.1f"),
        "vs S&P 500 (pp)": st.column_config.NumberColumn(format="%+.1f"),
        "From": st.column_config.DateColumn(format="MMM YYYY"),
        "To": st.column_config.DateColumn(format="MMM YYYY")})

    diffs = diff_files(cfg, ticker)
    with st.expander("What changed in the 10-K? (sentences added and removed)"):
        if diffs:
            pick = st.selectbox("Year", diffs, format_func=lambda p: p.stem.replace("_", " FY"))
            components.html(pick.read_text(), height=500, scrolling=True)
        else:
            st.write(f"No sentence diff saved for {ticker} yet. Make one with "
                     f"`python -m pilot diff --ticker {ticker} --fy <year>`, then reload.")

    st.download_button("Download all firm-years (CSV)", df.drop(columns="bin_label").to_csv(index=False),
                       file_name="lazy_prices_firm_years.csv", mime="text/csv")
