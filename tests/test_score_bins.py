from collections import Counter

import pandas as pd
import pytest

from pilot.bins import assign_bins
from pilot.score import cosine_similarity, jaccard_similarity, text_similarity

DOC = "the company faces risks related to competition and supply chain disruption.\nrevenue grew."


def test_identical_documents_score_one():
    cos, jac = text_similarity(DOC, DOC)
    assert cos == pytest.approx(1.0)
    assert jac == pytest.approx(1.0)


def test_disjoint_documents_score_zero():
    assert cosine_similarity(Counter("a b".split()), Counter("c d".split())) == 0.0
    assert jaccard_similarity({"a"}, {"b"}) == 0.0


def test_cosine_known_value():
    # vectors (1,1,0) and (1,0,1): cos = 1/2
    assert cosine_similarity(Counter(["x", "y"]), Counter(["x", "z"])) == pytest.approx(0.5)


def _sim(rows):
    return pd.DataFrame(rows, columns=["ticker", "fy", "cosine_sim"])


def test_lowest_similarity_gets_bin_1():
    df = _sim([("A", 2022, 0.90), ("B", 2022, 0.95), ("C", 2022, 0.80), ("D", 2022, 0.99), ("E", 2022, 0.85)])
    out, ties = assign_bins(df)
    bins = dict(zip(out.ticker, out.bin))
    assert bins == {"C": 1, "E": 2, "A": 3, "B": 4, "D": 5}
    assert ties == []


def test_ties_break_alphabetically_and_are_logged():
    df = _sim([("ZZ", 2022, 0.9), ("AA", 2022, 0.9), ("MM", 2022, 0.95), ("BB", 2022, 0.5), ("CC", 2022, 0.99)])
    out, ties = assign_bins(df)
    bins = dict(zip(out.ticker, out.bin))
    assert bins["AA"] < bins["ZZ"]
    assert ties == [{"fy": 2022, "value": 0.9, "tickers": ["AA", "ZZ"]}]


def test_bins_with_fewer_than_five_firms():
    df = _sim([("A", 2023, 0.7), ("B", 2023, 0.8), ("C", 2023, 0.9)])
    out, _ = assign_bins(df)
    # ceil(5*1/3)=2, ceil(5*2/3)=4, ceil(5*3/3)=5
    assert dict(zip(out.ticker, out.bin)) == {"A": 2, "B": 4, "C": 5}


def test_bins_ranked_within_each_year():
    df = _sim([("A", 2022, 0.1), ("B", 2022, 0.2), ("A", 2023, 0.9), ("B", 2023, 0.8)])
    out, _ = assign_bins(df)
    got = {(r.ticker, r.fy): r.bin for r in out.itertuples()}
    assert got[("A", 2022)] < got[("B", 2022)]
    assert got[("A", 2023)] > got[("B", 2023)]
