"""T2: pull the 10-K document out of each submission and reduce it to clean prose."""
from __future__ import annotations

import logging
import random
import re
import unicodedata
import warnings

import pandas as pd
from bs4 import BeautifulSoup, Comment, XMLParsedAsHTMLWarning

from pilot.config import Config, write_report
from pilot.t2_sections import SECTION_NAMES, extract_sections, section_path

log = logging.getLogger("pilot.t2_clean")
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

NUMERIC_TABLE_SHARE = 0.15  # Loughran-McDonald / Lazy Prices rule

_DOC_RE = re.compile(r"<DOCUMENT>(.*?)</DOCUMENT>", re.S | re.I)
_TYPE_RE = re.compile(r"<TYPE>\s*([^\s<]+)", re.I)
_TEXT_RE = re.compile(r"<TEXT>(.*)</TEXT>", re.S | re.I)
_IX_HEADER_RE = re.compile(r"<ix:header\b.*?</ix:header>", re.S | re.I)
_HIDDEN_STYLE_RE = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden", re.I)
_WORD_RE = re.compile(r"[a-z]+(?:'[a-z]+)?")

_BLOCK_TAGS = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6",
               "table", "ul", "ol", "section", "article", "hr", "center", "blockquote"}
_CELL_TAGS = {"td", "th"}
_QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"',
                         "–": "-", "—": "-", " ": " "})


class NoMainDocument(ValueError):
    pass


def extract_main_document(submission: str, form: str = "10-K") -> str:
    """Return the <TEXT> of the <DOCUMENT> whose <TYPE> is `form` (not exhibits/graphics)."""
    for m in _DOC_RE.finditer(submission):
        body = m.group(1)
        t = _TYPE_RE.search(body[:500])
        if t and t.group(1).strip().upper() == form.upper():
            txt = _TEXT_RE.search(body)
            return txt.group(1) if txt else body
    raise NoMainDocument(f"no <DOCUMENT> of type {form}")


def numeric_share(text: str) -> float:
    digits = sum(c.isdigit() for c in text)
    letters = sum(c.isalpha() for c in text)
    total = digits + letters
    return digits / total if total else 0.0


def html_to_text(html: str) -> tuple[str, dict]:
    """Strip hidden XBRL, hidden elements and numeric tables; return lowercase prose."""
    stats = {"tables_total": 0, "tables_removed": 0, "hidden_removed": 0}
    html = _IX_HEADER_RE.sub(" ", html)
    soup = BeautifulSoup(html, "lxml")

    for tag in soup.find_all(["script", "style", "head", "title"]):
        tag.decompose()
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for tag in soup.find_all("ix:header"):  # any the regex missed
        tag.decompose()
    for tag in soup.find_all(style=_HIDDEN_STYLE_RE):
        if not tag.decomposed:
            stats["hidden_removed"] += 1
            tag.decompose()
    for tag in soup.find_all(hidden=True):
        if not tag.decomposed:
            stats["hidden_removed"] += 1
            tag.decompose()

    tables = soup.find_all("table")
    stats["tables_total"] = len(tables)
    for tbl in tables:
        if tbl.decomposed:
            continue
        if numeric_share(tbl.get_text(" ")) > NUMERIC_TABLE_SHARE:
            stats["tables_removed"] += 1
            tbl.decompose()

    for tag in soup.find_all(True):
        if tag.name in _BLOCK_TAGS:
            tag.insert_before("\n")
            tag.append("\n")
        elif tag.name in _CELL_TAGS:
            tag.append(" ")
    return normalize_text(soup.get_text("")), stats


def plain_text_to_text(text: str) -> str:
    """Fallback for old plain-text submissions: drop lines that are mostly numbers."""
    keep = [ln for ln in text.splitlines() if numeric_share(ln) <= NUMERIC_TABLE_SHARE]
    return normalize_text("\n".join(keep))


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_QUOTES).lower()
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    lines = (ln.strip() for ln in text.split("\n"))
    return "\n".join(ln for ln in lines if ln) + "\n"


def tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text)


def _clean_document(doc: str) -> tuple[str, dict]:
    if re.search(r"<html|<body|<div|<p[ >]", doc[:5000], re.I):
        return html_to_text(doc)
    return plain_text_to_text(doc), {"tables_total": 0, "tables_removed": 0, "hidden_removed": 0}


def clean_submission(raw: str) -> tuple[str, dict]:
    return _clean_document(extract_main_document(raw, "10-K"))


def clean_exhibit13(raw: str) -> str | None:
    """Clean text of the EX-13 annual report, if the submission has one. Some filers
    incorporate MD&A into the 10-K by reference from it."""
    try:
        doc = extract_main_document(raw, "EX-13")
    except NoMainDocument:
        return None
    return _clean_document(doc)[0]


def run_clean(cfg: Config) -> pd.DataFrame:
    from pilot.cli import CheckFailed
    from pilot.t1_download import load_manifest

    p = cfg.paths
    p.clean.mkdir(parents=True, exist_ok=True)
    p.sections.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(cfg)
    rows, gaps, sec_rows = [], [], []
    missing_sections = []
    for r in manifest.itertuples():
        out = p.clean / f"{r.cik}_{r.fy}.txt"
        raw = (p.root / r.path).read_text(encoding="utf-8", errors="replace")
        try:
            text, stats = clean_submission(raw)
        except NoMainDocument as e:
            gaps.append(f"{r.ticker} FY{r.fy}: {e}")
            continue
        out.write_text(text, encoding="utf-8")
        found = extract_sections(text, clean_exhibit13(raw), cfg.sections)
        for sec, (sec_text, info) in found.items():
            sp = section_path(cfg, r.cik, r.fy, sec)
            if sec_text:
                sp.write_text(sec_text, encoding="utf-8")
            else:
                sp.unlink(missing_ok=True)
                missing_sections.append(f"{r.ticker} FY{r.fy}: {SECTION_NAMES[sec]}")
                gaps.append(f"{r.ticker} FY{r.fy}: {SECTION_NAMES[sec]} not found "
                            f"(longest candidate {info['n_words']} words); filing not scored")
            sec_rows.append({"ticker": r.ticker, "fy": r.fy, "section": sec,
                             "n_words": len(tokenize(sec_text)), "source": info["source"],
                             "heading": info["heading"], "lines": f"{info['start_line']}-{info['end_line']}"})
        n = len(tokenize(text))
        rows.append({"ticker": r.ticker, "cik": r.cik, "fy": r.fy, "n_words": n,
                     "path": str(out.relative_to(p.root)), **stats})
        log.info("%s FY%d: %d words (%d/%d tables removed as numeric)", r.ticker, r.fy, n,
                 stats["tables_removed"], stats["tables_total"])

    wc = pd.DataFrame(rows)
    wc.to_csv(p.clean / "word_counts.csv", index=False)
    secs = pd.DataFrame(sec_rows)
    secs.to_csv(p.sections / "section_word_counts.csv", index=False)
    smed = secs.groupby(["ticker", "section"])["n_words"].transform("median")
    secs["ratio_to_median"] = (secs["n_words"] / smed).round(3)
    sec_outliers = secs[(secs["n_words"] > 0) & ((secs["ratio_to_median"] > 3) | (secs["ratio_to_median"] < 1 / 3))]

    # ---- check
    med = wc.groupby("ticker")["n_words"].transform("median")
    wc["ratio_to_median"] = (wc["n_words"] / med).round(3)
    flagged = wc[(wc["ratio_to_median"] > 3) | (wc["ratio_to_median"] < 1 / 3)]
    leftovers = []
    for r in wc.itertuples():
        t = (p.root / r.path).read_text(encoding="utf-8")
        hits = re.findall(r"<[a-z/!][^>]{0,40}>|&[a-z]+;|&#\d+;|ix:|xbrli|us-gaap:", t)
        if len(hits) > 20:
            leftovers.append((r.ticker, r.fy, len(hits), hits[:5]))

    sample = random.Random(0).sample(list(wc.itertuples()), k=min(3, len(wc)))
    report = {
        "files": len(wc), "manifest_rows": len(manifest), "gaps": gaps,
        "word_counts": wc[["ticker", "fy", "n_words", "ratio_to_median"]].to_dict("records"),
        "size_outliers": flagged[["ticker", "fy", "n_words", "ratio_to_median"]].to_dict("records"),
        "markup_leftovers": leftovers, "spot_check": [s.path for s in sample],
        "sections": cfg.sections,
        "section_word_counts": secs[["ticker", "fy", "section", "n_words", "source"]].to_dict("records"),
        "section_outliers": sec_outliers[["ticker", "fy", "section", "n_words", "ratio_to_median"]].to_dict("records"),
        "sections_from_exhibit": secs[secs["source"] == "EX-13"][["ticker", "fy", "section"]].to_dict("records"),
    }
    write_report(cfg, "clean", report)
    print(f"\n[T2 check] clean files: {len(wc)} / {len(manifest)} manifest rows")
    print(wc.pivot(index="ticker", columns="fy", values="n_words").to_string())
    print(f"[T2 check] size outliers (>3x or <1/3 of firm median): "
          f"{report['size_outliers'] or 'none'}")
    print(f"[T2 check] files with leftover markup: {leftovers or 'none'}")
    for sec in cfg.sections:
        print(f"\n[T2 check] {SECTION_NAMES[sec]} words (0 = not found):")
        print(secs[secs.section == sec].pivot(index="ticker", columns="fy", values="n_words").to_string())
    ex = report["sections_from_exhibit"]
    print(f"[T2 check] sections taken from an EX-13 exhibit: "
          f"{[(x['ticker'], x['fy'], x['section']) for x in ex] or 'none'}")
    print(f"[T2 check] section size outliers (>3x or <1/3 of firm median): "
          f"{report['section_outliers'] or 'none'}")
    print(f"[T2 check] gaps: {gaps or 'none'}")
    for s in sample:
        body = (p.root / s.path).read_text(encoding="utf-8")
        mid = len(body) // 2
        print(f"\n--- spot check {s.ticker} FY{s.fy} ({s.path}) ---\n{body[mid:mid + 600]}")
    if len(wc) < len(manifest) - len(gaps):
        raise CheckFailed("some filings have no clean file")
    if missing_sections:
        raise CheckFailed(f"{len(missing_sections)} section(s) not found, so those filings cannot be scored; "
                          f"check the headings and add a pattern in t2_sections.py: {missing_sections}")
    if leftovers:
        raise CheckFailed(f"markup left in clean text: {leftovers}")
    return wc
