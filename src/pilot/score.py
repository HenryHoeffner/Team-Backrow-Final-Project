"""T3: similarity of each 10-K to the same firm's prior-year 10-K."""
from __future__ import annotations

import logging
import math
from collections import Counter

import pandas as pd

from pilot.clean import tokenize
from pilot.config import Config, write_report

log = logging.getLogger("pilot.score")

SIM_COLUMNS = ["ticker", "cik", "fy", "prev_fy", "filing_date", "cosine_sim", "jaccard_sim",
               "n_words", "n_words_prev"]


def cosine_similarity(a: Counter, b: Counter) -> float:
    """Cosine of two word-count vectors. 1 = identical word mix, 0 = no shared words."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    small, large = (a, b) if len(a) <= len(b) else (b, a)
    dot = math.fsum(v * large[w] for w, v in small.items() if w in large)
    na = math.sqrt(math.fsum(v * v for v in a.values()))
    nb = math.sqrt(math.fsum(v * v for v in b.values()))
    return min(1.0, max(0.0, dot / (na * nb)))


def jaccard_similarity(a: Counter | set, b: Counter | set) -> float:
    """Shared distinct words / all distinct words."""
    sa, sb = set(a), set(b)
    union = sa | sb
    return len(sa & sb) / len(union) if union else 0.0


def text_similarity(text_a: str, text_b: str) -> tuple[float, float]:
    ca, cb = Counter(tokenize(text_a)), Counter(tokenize(text_b))
    return cosine_similarity(ca, cb), jaccard_similarity(ca, cb)


def run_score(cfg: Config) -> pd.DataFrame:
    from pilot.cli import CheckFailed
    from pilot.download import load_manifest

    p = cfg.paths
    manifest = load_manifest(cfg).set_index(["ticker", "fy"])
    years = sorted(manifest.index.get_level_values("fy").unique())
    counts: dict[tuple[str, int], Counter] = {}

    def words(ticker: str, fy: int) -> Counter | None:
        if (ticker, fy) not in counts:
            if (ticker, fy) not in manifest.index:
                return None
            path = p.clean / f"{manifest.loc[(ticker, fy), 'cik']}_{fy}.txt"
            if not path.exists():
                return None
            counts[(ticker, fy)] = Counter(tokenize(path.read_text(encoding="utf-8")))
        return counts[(ticker, fy)]

    rows, gaps = [], []
    for firm in cfg.firms:
        for fy in years[1:]:
            cur, prev = words(firm.ticker, fy), words(firm.ticker, fy - 1)
            if cur is None or prev is None:
                gaps.append(f"{firm.ticker} FY{fy}: missing {'current' if cur is None else 'prior-year'} clean text")
                continue
            rows.append({
                "ticker": firm.ticker, "cik": firm.cik, "fy": fy, "prev_fy": fy - 1,
                "filing_date": manifest.loc[(firm.ticker, fy), "filing_date"],
                "cosine_sim": cosine_similarity(cur, prev), "jaccard_sim": jaccard_similarity(cur, prev),
                "n_words": sum(cur.values()), "n_words_prev": sum(prev.values()),
            })
    sim = pd.DataFrame(rows, columns=SIM_COLUMNS)
    sim["filing_date"] = pd.to_datetime(sim["filing_date"])
    sim.to_parquet(p.similarity, index=False)

    # ---- check
    expected = len(cfg.firms) * (len(years) - 1)
    in_range = bool(sim[["cosine_sim", "jaccard_sim"]].apply(lambda s: s.between(0, 1)).all().all())
    lowest = sim.nsmallest(3, "cosine_sim")
    write_report(cfg, "score", {"rows": len(sim), "expected_rows": expected, "gaps": gaps,
                                "in_range": in_range,
                                "lowest": lowest[["ticker", "fy", "cosine_sim", "jaccard_sim"]].to_dict("records")})
    print(f"\n[T3 check] similarity rows: {len(sim)} (expected {expected}); all scores in [0, 1]: {in_range}")
    print(sim.pivot(index="ticker", columns="fy", values="cosine_sim").round(4).to_string())
    print("\n[T3 check] three lowest-similarity filings (review these):")
    print(lowest[["ticker", "fy", "prev_fy", "cosine_sim", "jaccard_sim", "n_words", "n_words_prev"]]
          .to_string(index=False))
    if not in_range:
        raise CheckFailed("similarity outside [0, 1]")
    return sim
