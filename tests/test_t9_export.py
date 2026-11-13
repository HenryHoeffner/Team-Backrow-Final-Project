import pandas as pd

from pilot.t9_export import FIRM_YEAR_COLUMNS, firm_summary, firm_year_table


class _Firm:
    def __init__(self, ticker):
        self.ticker, self.name, self.sector = ticker, ticker + " Inc", "Tech"


class _Cfg:
    firms = [_Firm("AAA"), _Firm("BBB")]


def _tables():
    sim = pd.DataFrame({"ticker": ["AAA", "AAA", "BBB"], "fy": [2020, 2021, 2020], "prev_fy": [2019, 2020, 2019],
                        "filing_date": pd.to_datetime(["2021-02-01", "2022-02-01", "2021-02-01"]).date,
                        "cosine_sim": .9, "jaccard_sim": .5, "cosine_risk_factors": .9, "cosine_mdna": .9,
                        "change": .1, "prior_median_change": .1, "rel_change": 1.0, "bin": [1, 5, None]})
    ret = pd.DataFrame({"ticker": ["AAA", "AAA", "BBB"], "fy": [2020, 2021, 2020],
                        "filing_date": sim["filing_date"], "window_start": sim["filing_date"], "window_end": sim["filing_date"],
                        "firm_return_pct": [10., 5., 3.], "spy_return_pct": [4., 8., 1.],
                        "excess_return_pct": [6., -3., 2.], "partial": [False, True, False]})
    return sim, ret


def test_firm_year_table_joins_one_row_per_filing():
    fy = firm_year_table(_Cfg(), *_tables())
    assert list(fy.columns) == FIRM_YEAR_COLUMNS and len(fy) == 3
    assert fy.loc[fy.ticker == "AAA", "name"].iloc[0] == "AAA Inc"
    assert fy["bin"].isna().sum() == 1  # BBB has no bin yet


def test_firm_summary_ignores_open_windows():
    s = firm_summary(firm_year_table(_Cfg(), *_tables())).set_index("ticker")
    assert s.loc["AAA", "years_with_full_window"] == 1 and s.loc["AAA", "avg_excess_return_pct"] == 6.0
    assert s.loc["AAA", "years_in_Q1"] == 1 and s.loc["AAA", "years_in_Q5"] == 0
