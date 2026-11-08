"""T2 (part 2): cut Item 1A (Risk Factors) and Item 7 (MD&A) out of a cleaned 10-K.

The five firms lay out their 10-Ks differently:
  CAT, PFE   standard "Item 1A. Risk Factors" / "Item 7. Management's Discussion ..." headings
  JPM        standard Item 1A; MD&A sits in the annual-report part with a page running header
  MCD, INTC  their own order with a cross-reference index; sections have plain-name headings

So a section is found from heading lines rather than Item numbers alone. A heading line
is a short line (the cleaner keeps HTML block breaks as line breaks). Every line that
looks like the section's start heading is a candidate start, and its span runs to the next
heading that starts a different section. The table of contents and cross-reference index
also contain these headings, but there the next heading follows within a line or two,
so the longest span is the real section.

If a filing incorporates a section by reference from another document (an EX-13 annual
report), the section in the 10-K document is only a pointer; the caller can then search
the exhibit text instead.
"""
from __future__ import annotations

import re

SECTION_NAMES = {"risk_factors": "Item 1A: Risk Factors", "mdna": "Item 7: MD&A"}

MAX_HEADING_WORDS = 15
MIN_SECTION_WORDS = 1000  # shorter than this is a pointer ("see page 40"), not the section

_ITEM_ALONE = re.compile(r"^item \d+[a-d]?[.:]?$")
# NEM appends its units note to every heading: "item 1a. risk factors (dollars in millions, except ...)"
_UNITS_NOTE = re.compile(r"\s*\((?:dollars|amounts|in millions)[^)]*\)\s*$")
_PAGE = r"(?:\s+\d{1,3})?"  # trailing page number in an index line

_START = {
    "risk_factors": [
        rf"^(?:item 1a\b[.:]?\s*[-:]?\s*)?risk factors\.?{_PAGE}$",
        # MCD FY2015-2018: "item 1a. risk factors and cautionary statement regarding forward-looking statements"
        r"^item 1a\b[.:]?\s*risk factors and cautionary statement (?:regarding|about) forward-looking"
        r" (?:statements|information)\.?$",
    ],
    "mdna": [
        rf"^(?:item 7\b[.:]?\s*[-:]?\s*)?management'?s discussion and analysis"
        rf"(?: of (?:the )?(?:consolidated )?financial condition(?: and results(?: of operations?)?)?)?\.?{_PAGE}$",
        # COP FY2019-2020: the Item 7 title wraps after "and" onto the next line.
        r"^item 7\b[.:]?\s*management'?s discussion and$",
        # INTC FY2017-2018: "management's discussion and analysis (md&a) - results of operations"
        r"^management'?s discussion and analysis \(md&a\)(?: -.*)?$",
    ],
}

# Extra start headings tried only in an EX-13 annual-report exhibit. PFE FY2015-2019
# incorporate MD&A by reference from its "Financial Review".
_EXHIBIT_START = {
    "risk_factors": [],
    "mdna": [r"^financial review$"],
}

_END = {
    "risk_factors": [
        r"^item (?:1b|1c|1d|[2-9]|1[0-6])\b",
        r"^unresolved staff comments\b",
        r"^cybersecurity\.?$",
        r"^properties\.?$",
        r"^legal proceedings\b",
        r"^sales and marketing$",                       # INTC: "other key information" part
        r"^quantitative and qualitative disclosures? about market risks?\b",  # HON writes "risks"
        r"^financial statements\b",
        r"^management'?s discussion and analysis\b",    # where MD&A follows risk factors
        r"^information about our executive officers\b",
        r"^executive officers of the registrant\b",
    ],
    "mdna": [
        r"^item (?:7a|8|9|9a|1[0-6])\b",
        r"^quantitative and qualitative disclosures? about market risks?\b",  # HON writes "risks"
        r"^financial statements and (?:supplementary data|supplemental details)\b",
        r"^management'?s report on internal control\b",
        r"^report of independent registered public accounting firm\b",
        r"^risk factors(?: and other key information)?\.?$",  # INTC, MCD put risk factors after MD&A
        r"^other key information$",                          # MCD
        r"^item 1a\b",
    ],
}

_START_RE = {k: [re.compile(p) for p in v] for k, v in _START.items()}
_EXHIBIT_START_RE = {k: [re.compile(p) for p in v] for k, v in _EXHIBIT_START.items()}
_END_RE = {k: [re.compile(p) for p in v] for k, v in _END.items()}
_ITEM_END_RE = {k: [re.compile(p) for p in v if p.startswith("^item")] for k, v in _END.items()}


def _heading_lines(lines: list[str]) -> list[tuple[int, str]]:
    """(line index, heading text) for short lines. A bare "item 7." line is joined to the
    next line, since some filings put the item number and title in separate cells."""
    out = []
    for i, ln in enumerate(lines):
        text = _UNITS_NOTE.sub("", ln.strip())
        if len(text.split()) > MAX_HEADING_WORDS:
            continue
        if _ITEM_ALONE.match(text) and i + 1 < len(lines):
            text = f"{text} {lines[i + 1].strip()}"
        out.append((i, text))
    return out


def _matches(text: str, patterns: list[re.Pattern]) -> bool:
    return any(p.match(text) for p in patterns)


def find_section(text: str, section: str, exhibit: bool = False) -> tuple[str, dict]:
    """Return (section text, info). Section text is "" if no span reaches MIN_SECTION_WORDS.

    info has the chosen start/end line numbers (1-based), the heading text, the word
    count, and how many candidate starts were seen. `exhibit=True` also accepts the
    headings an EX-13 annual report uses.
    """
    starts = _START_RE[section] + (_EXHIBIT_START_RE[section] if exhibit else [])
    lines = text.split("\n")
    heads = _heading_lines(lines)
    # Two tiers. A start heading that carries its Item number ("item 7. management's ...")
    # runs to the next Item heading, so sub-headings such as CAT's "risk factors" pointer
    # inside MD&A cannot cut it short. A plain-name heading ("risk factors") runs to the
    # next section name. The plain-name tier is used only when no Item-numbered span is
    # long enough, i.e. for filings (INTC, MCD) that use Item numbers only in an index.
    best: dict[int, tuple[int, int, int, str]] = {}  # tier -> (n_words, start, end, heading)
    n_candidates = 0
    for k, (i, head) in enumerate(heads):
        if not _matches(head, starts):
            continue
        n_candidates += 1
        tier = 0 if head.startswith("item ") else 1
        ends = _ITEM_END_RE[section] if tier == 0 else _END_RE[section]
        joined = _ITEM_ALONE.match(lines[i].strip()) is not None
        end = len(lines)
        for j, nxt in heads[k + 1:]:
            if joined and j == i + 1:  # the title line already joined to this "item N." line
                continue
            if _matches(nxt, ends):
                end = j
                break
        n_words = sum(len(ln.split()) for ln in lines[i + 1:end])
        if tier not in best or n_words > best[tier][0]:
            best[tier] = (n_words, i, end, head)
    info = {"candidates": n_candidates, "n_words": 0, "start_line": None, "end_line": None,
            "heading": None}
    if not best:
        return "", info
    if 0 in best and best[0][0] >= MIN_SECTION_WORDS:
        n_words, i, end, head = best[0]
    else:
        n_words, i, end, head = max(best.values())
    info.update(n_words=n_words, start_line=i + 1, end_line=end, heading=head)
    if n_words < MIN_SECTION_WORDS:
        return "", info
    return "\n".join(lines[i:end]).strip() + "\n", info


def extract_sections(main: str, exhibit: str | None, sections: list[str]) -> dict[str, tuple[str, dict]]:
    """Find each section in the 10-K document; if it is only a pointer there and the
    submission has an EX-13 annual report, look in the exhibit. info["source"] says which."""
    out = {}
    for s in sections:
        text, info = find_section(main, s)
        info["source"] = "10-K"
        if not text and exhibit:
            ex_text, ex_info = find_section(exhibit, s, exhibit=True)
            if ex_text:
                text, info = ex_text, {**ex_info, "source": "EX-13"}
        out[s] = (text, info)
    return out


# --------------------------------------------------------------------------- files


def section_path(cfg, cik: str, fy: int, section: str):
    return cfg.paths.sections / f"{cik}_{fy}_{section}.txt"


def load_scored_text(cfg, cik: str, fy: int) -> dict[str, str] | None:
    """The configured sections of one filing, or None if any is missing."""
    out = {}
    for s in cfg.sections:
        path = section_path(cfg, cik, fy, s)
        if not path.exists():
            return None
        out[s] = path.read_text(encoding="utf-8")
    return out
