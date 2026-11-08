"""T3: similarity of each 10-K to the same firm's prior-year 10-K."""
from __future__ import annotations

import logging
import math
from collections import Counter

import pandas as pd

from pilot.t2_clean import tokenize
from pilot.t2_sections import load_scored_text
from pilot.config import Config, write_report

log = logging.getLogger("pilot.t3_score")

SIM_COLUMNS = ["ticker", "cik", "fy", "prev_fy", "filing_date", "cosine_sim", "jaccard_sim",
               "n_words", "n_words_prev"]
# Per-section columns (cosine_<section>, n_words_<section>) follow for each configured section.


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
    from pilot.t1_download import load_manifest

    p = cfg.paths
    manifest = load_manifest(cfg).set_index(["ticker", "fy"])
    years = sorted(manifest.index.get_level_values("fy").unique())
    counts: dict[tuple[str, int], dict[str, Counter] | None] = {}

    def words(ticker: str, fy: int) -> dict[str, Counter] | None:
        """Word counts per configured section, plus "all" = the sections scored together."""
        if (ticker, fy) not in counts:
            texts = None
            if (ticker, fy) in manifest.index:
                texts = load_scored_text(cfg, manifest.loc[(ticker, fy), "cik"], fy)
            if texts is None:
                counts[(ticker, fy)] = None
            else:
                c = {s: Counter(tokenize(t)) for s, t in texts.items()}
                c["all"] = sum(c.values(), Counter())
                counts[(ticker, fy)] = c
        return counts[(ticker, fy)]

    rows, gaps = [], []
    for firm in cfg.firms:
        for fy in years[1:]:
            cur, prev = words(firm.ticker, fy), words(firm.ticker, fy - 1)
            if cur is None or prev is None:
                gaps.append(f"{firm.ticker} FY{fy}: missing {'current' if cur is None else 'prior-year'} "
                            f"section text ({', '.join(cfg.sections)})")
                continue
            row = {
                "ticker": firm.ticker, "cik": firm.cik, "fy": fy, "prev_fy": fy - 1,
                "filing_date": manifest.loc[(firm.ticker, fy), "filing_date"],
                "cosine_sim": cosine_similarity(cur["all"], prev["all"]),
                "jaccard_sim": jaccard_similarity(cur["all"], prev["all"]),
                "n_words": sum(cur["all"].values()), "n_words_prev": sum(prev["all"].values()),
            }
            for sec in cfg.sections:
                row[f"cosine_{sec}"] = cosine_similarity(cur[sec], prev[sec])
                row[f"n_words_{sec}"] = sum(cur[sec].values())
            rows.append(row)
    sec_cols = [f"{k}_{s}" for s in cfg.sections for k in ("cosine", "n_words")]
    sim = pd.DataFrame(rows, columns=SIM_COLUMNS + sec_cols)
    sim["filing_date"] = pd.to_datetime(sim["filing_date"])
    sim.to_parquet(p.similarity, index=False)

    # ---- check
    expected = len(cfg.firms) * (len(years) - 1)
    score_cols = ["cosine_sim", "jaccard_sim"] + [f"cosine_{s}" for s in cfg.sections]
    in_range = bool(sim[score_cols].apply(lambda s: s.between(0, 1)).all().all())
    lowest = sim.nsmallest(3, "cosine_sim")
    write_report(cfg, "score", {"rows": len(sim), "expected_rows": expected, "gaps": gaps,
                                "in_range": in_range, "sections": cfg.sections,
                                "lowest": lowest[["ticker", "fy", "cosine_sim", "jaccard_sim"]].to_dict("records")})
    print(f"\n[T3 check] similarity rows: {len(sim)} (expected {expected}); all scores in [0, 1]: {in_range}")
    print(f"Text scored: {' + '.join(cfg.sections)}")
    print(sim.pivot(index="ticker", columns="fy", values="cosine_sim").round(4).to_string())
    for sec in cfg.sections:
        print(f"\ncosine, {sec} only:")
        print(sim.pivot(index="ticker", columns="fy", values=f"cosine_{sec}").round(4).to_string())
    print("\n[T3 check] three lowest-similarity filings (review these):")
    print(lowest[["ticker", "fy", "prev_fy", "cosine_sim", "jaccard_sim", "n_words", "n_words_prev"]]
          .to_string(index=False))
    if not in_range:
        raise CheckFailed("similarity outside [0, 1]")
    return sim
