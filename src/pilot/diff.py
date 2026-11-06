"""T8 (stretch): HTML listing sentences added and removed between two cleaned 10-Ks."""
from __future__ import annotations

import difflib
import html
import re

import pandas as pd

from pilot.config import Config

_SENT_SPLIT = re.compile(r"(?<=[.!?;])\s+|\n+")


def sentences(text: str) -> list[str]:
    out = []
    for s in _SENT_SPLIT.split(text):
        s = s.strip()
        if len(re.findall(r"[a-z]{2,}", s)) >= 4:  # skip headings, page numbers, fragments
            out.append(s)
    return out


def _key(sentence: str) -> str:
    """Mask digits so a sentence that only rolled its year or figures forward still matches."""
    return re.sub(r"\d[\d,.]*", "#", sentence)


def sentence_diff(old: str, new: str) -> tuple[list[str], list[str]]:
    a, b = sentences(old), sentences(new)
    ka, kb = [_key(s) for s in a], [_key(s) for s in b]
    added, removed = [], []
    sm = difflib.SequenceMatcher(None, ka, kb, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op in ("delete", "replace"):
            removed.extend(range(i1, i2))
        if op in ("insert", "replace"):
            added.extend(range(j1, j2))
    # A sentence that only moved is not a change.
    ka_set, kb_set = {ka[i] for i in removed}, {kb[j] for j in added}
    return ([b[j] for j in added if kb[j] not in ka_set],
            [a[i] for i in removed if ka[i] not in kb_set])


def render_html(ticker: str, fy: int, cos: float, added: list[str], removed: list[str]) -> str:
    def items(xs):
        return "\n".join(f"<li>{html.escape(x)}</li>" for x in xs)
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{ticker} FY{fy} 10-K changes</title>
<style>
:root {{ --bg:#fff; --ink:#222; --muted:#666; --add:#e8f5e9; --addb:#1a9e1a; --rem:#fdecea; --remb:#e41a1c; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#16181b; --ink:#e6e6e6; --muted:#9a9a9a;
  --add:#16301a; --addb:#5cc85c; --rem:#3a1a1a; --remb:#ff6b6b; }} }}
body {{ background:var(--bg); color:var(--ink); font:15px/1.5 system-ui, sans-serif;
  max-width:980px; margin:0 auto; padding:24px 16px; }}
p.meta {{ color:var(--muted); }}
details {{ margin:16px 0; }} summary {{ font-weight:600; cursor:pointer; font-size:17px; }}
li {{ margin:6px 0; padding:6px 10px; border-left:3px solid; list-style:none; }}
ul {{ padding:0; }}
.add li {{ background:var(--add); border-color:var(--addb); }}
.rem li {{ background:var(--rem); border-color:var(--remb); }}
</style></head><body>
<h1>{ticker}: FY{fy} 10-K vs FY{fy - 1}</h1>
<p class="meta">Cosine similarity {cos:.4f}. Sentences with fewer than 4 words are skipped; sentences that
only moved, or only changed numbers or years, are not listed. Text is the cleaned, lowercased 10-K used for scoring.</p>
<details open class="add"><summary>Added in FY{fy} ({len(added):,})</summary><ul>{items(added)}</ul></details>
<details open class="rem"><summary>Removed from FY{fy - 1} ({len(removed):,})</summary><ul>{items(removed)}</ul></details>
</body></html>
"""


def run_diff(cfg: Config, ticker: str | None = None, fy: int | None = None, lowest: int | None = None):
    p = cfg.paths
    sim = pd.read_parquet(p.similarity)
    if lowest:
        targets = sim.nsmallest(lowest, "cosine_sim")[["ticker", "fy"]].itertuples(index=False)
    elif ticker and fy:
        targets = [(ticker.upper(), fy)]
    else:
        raise SystemExit("give --ticker and --fy, or --lowest N")
    p.diffs.mkdir(parents=True, exist_ok=True)
    for t, y in targets:
        row = sim[(sim.ticker == t) & (sim.fy == y)]
        if row.empty:
            raise SystemExit(f"no similarity row for {t} FY{y}")
        cik = row.iloc[0]["cik"]
        new = (p.clean / f"{cik}_{y}.txt").read_text(encoding="utf-8")
        old = (p.clean / f"{cik}_{y - 1}.txt").read_text(encoding="utf-8")
        added, removed = sentence_diff(old, new)
        out = p.diffs / f"{t}_{y}.html"
        out.write_text(render_html(t, int(y), float(row.iloc[0]["cosine_sim"]), added, removed), encoding="utf-8")
        print(f"{out.relative_to(p.root)}: {len(added)} added, {len(removed)} removed sentences")
