"""T1: download 10-K filings from EDGAR and build the filings manifest.

Downloaded files are treated as untrusted text: they are only read and parsed,
never executed.
"""
from __future__ import annotations

import logging
import os
import random
import re
import threading
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from pilot.config import Config, write_report

log = logging.getLogger("pilot.download")

FILED_AFTER = "2021-01-01"
MIN_SECONDS_BETWEEN_REQUESTS = 0.25  # about 4 requests/second, well under the SEC's 10
MAX_RETRIES = 5
HEADER_BYTES = 64_000

_HEADER_FIELDS = {
    "accession": r"ACCESSION NUMBER:\s*(\S+)",
    "form": r"CONFORMED SUBMISSION TYPE:\s*(\S+)",
    "period_of_report": r"CONFORMED PERIOD OF REPORT:\s*(\d{8})",
    "filing_date": r"FILED AS OF DATE:\s*(\d{8})",
    "company_name": r"COMPANY CONFORMED NAME:\s*(.+?)\s*$",
    "cik": r"CENTRAL INDEX KEY:\s*(\d+)",
}


# --------------------------------------------------------------------------- header


def parse_sec_header(text: str) -> dict:
    """Parse the <SEC-HEADER> block of a full-submission.txt.

    Returns accession, form, period_of_report (date), filing_date (date),
    company_name and cik (10 digits). For multi-filer submissions the first
    filer is used.
    """
    end = text.find("</SEC-HEADER>")
    header = text[: end if end != -1 else HEADER_BYTES]
    out: dict = {}
    for key, pattern in _HEADER_FIELDS.items():
        m = re.search(pattern, header, flags=re.MULTILINE)
        out[key] = m.group(1).strip() if m else None
    for key in ("period_of_report", "filing_date"):
        if out[key]:
            out[key] = datetime.strptime(out[key], "%Y%m%d").date()
    if out["cik"]:
        out["cik"] = out["cik"].zfill(10)
    return out


def normalize_name(name: str) -> str:
    """Uppercase and drop punctuation/spaces so "McDonald's Corp" == "MCDONALDS CORP"."""
    return re.sub(r"[^A-Z0-9]", "", name.upper().replace("&", ""))


def names_match(header_name: str, config_name: str) -> bool:
    return normalize_name(header_name) == normalize_name(config_name)


# --------------------------------------------------------------------------- SEC access


def _sec_identity() -> tuple[str, str]:
    name = os.environ.get("SEC_USER_NAME", "").strip()
    email = os.environ.get("SEC_USER_EMAIL", "").strip()
    if not name or not email:
        raise SystemExit(
            "SEC_USER_NAME and SEC_USER_EMAIL must be set in the environment "
            "(the SEC requires a declared identity in the User-Agent)."
        )
    return name, email


def _install_throttle_and_retries() -> None:
    """Wrap sec-edgar-downloader's single HTTP entry point with a slower
    throttle and retries. The library's own limiter allows the full 10 req/s
    and does not retry."""
    import requests
    from sec_edgar_downloader import _sec_gateway as gw

    if getattr(gw._call_sec, "_pilot_wrapped", False):
        return
    inner = gw._call_sec
    lock = threading.Lock()
    last = [0.0]

    def throttled(uri, user_agent, host):
        for attempt in range(1, MAX_RETRIES + 1):
            with lock:
                wait = MIN_SECONDS_BETWEEN_REQUESTS - (time.monotonic() - last[0])
                if wait > 0:
                    time.sleep(wait)
                last[0] = time.monotonic()
            try:
                return inner(uri, user_agent, host)
            except requests.HTTPError as e:
                status = e.response.status_code if e.response is not None else None
                if status not in (403, 429, 500, 502, 503, 504) or attempt == MAX_RETRIES:
                    raise
                err = f"HTTP {status}"
            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt == MAX_RETRIES:
                    raise
                err = type(e).__name__
            backoff = 2 ** attempt + random.Random(attempt).random()
            log.warning("%s on %s; retry %d/%d in %.1fs", err, uri, attempt, MAX_RETRIES, backoff)
            time.sleep(backoff)

    throttled._pilot_wrapped = True  # type: ignore[attr-defined]
    gw._call_sec = throttled


# --------------------------------------------------------------------------- discovery


def discover_submissions(raw_dir: Path) -> list[tuple[Path, dict]]:
    """Find every full-submission.txt under raw_dir (layout not assumed) and parse its header."""
    found = []
    for path in sorted(raw_dir.rglob("full-submission.txt")):
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            head = fh.read(HEADER_BYTES)
        found.append((path, parse_sec_header(head)))
    return found


def _audit_forms(cfg: Config, user_agent: str) -> list[dict]:
    """List every 10-K-family filing in the submissions index so amendments and
    transition reports are flagged, not silently skipped."""
    from sec_edgar_downloader import _sec_gateway as gw

    base = "https://data.sec.gov/submissions/"
    rows = []
    for firm in cfg.firms:
        first = gw.get_list_of_available_filings(f"{base}CIK{firm.cik.zfill(10)}.json", user_agent)
        pages = [first["filings"]["recent"]]
        # Prolific filers (JPM issues thousands of notes) spill older filings into extra pages.
        for extra in first["filings"].get("files", []):
            if extra.get("filingTo", "9999") >= FILED_AFTER:
                pages.append(gw.get_list_of_available_filings(base + extra["name"], user_agent))
        for page in pages:
            for acc, form, fdate, rdate in zip(
                page["accessionNumber"], page["form"], page["filingDate"], page["reportDate"]
            ):
                if form.startswith("10-K") and fdate >= FILED_AFTER:
                    rows.append({"ticker": firm.ticker, "accession": acc, "form": form,
                                 "filing_date": fdate, "report_date": rdate})
    return sorted(rows, key=lambda r: (r["ticker"], r["filing_date"]))


# --------------------------------------------------------------------------- main step


def run_download(cfg: Config, fetch: bool = True) -> pd.DataFrame:
    p = cfg.paths
    p.raw.mkdir(parents=True, exist_ok=True)
    report: dict = {"gaps": [], "notes": []}

    if fetch:
        from sec_edgar_downloader import Downloader

        name, email = _sec_identity()
        _install_throttle_and_retries()
        dl = Downloader(name, email, p.raw)
        on_disk = {h["accession"] for _, h in discover_submissions(p.raw) if h["accession"]}
        for firm in cfg.firms:
            n = dl.get("10-K", firm.cik, after=FILED_AFTER, download_details=True,
                       accession_numbers_to_skip=on_disk)
            log.info("%s: %d new 10-K submission(s) downloaded", firm.ticker, n)
        audit = _audit_forms(cfg, dl.user_agent)
        pd.DataFrame(audit).to_csv(p.data / "form_audit.csv", index=False)
        report["amendments_dropped"] = [r for r in audit if r["form"] == "10-K/A"]
        report["transition_reports_flagged"] = [r for r in audit if r["form"] == "10-KT"]

    rows, name_mismatch = [], []
    for path, h in discover_submissions(p.raw):
        firm = cfg.firm_by_cik(h["cik"] or "")
        if firm is None:
            log.warning("ignoring %s: CIK %s not in config", path, h["cik"])
            continue
        if not names_match(h["company_name"] or "", firm.name):
            name_mismatch.append({"ticker": firm.ticker, "header": h["company_name"], "config": firm.name})
        if h["form"] == "10-KT":
            report.setdefault("transition_reports_flagged", []).append(
                {"ticker": firm.ticker, "accession": h["accession"]})
            continue
        if h["form"] != "10-K":
            continue  # 10-K/A and anything else
        fy = h["period_of_report"].year
        rows.append({
            "ticker": firm.ticker, "cik": firm.cik, "accession": h["accession"], "form": h["form"],
            "period_of_report": h["period_of_report"], "filing_date": h["filing_date"], "fy": fy,
            "path": str(path.relative_to(p.root)),
        })

    m = pd.DataFrame(rows, columns=["ticker", "cik", "accession", "form", "period_of_report",
                                    "filing_date", "fy", "path"])
    years = list(cfg.fiscal_years)
    m = m[m["fy"].between(years[0], years[-1])]

    dup = m[m.duplicated(["ticker", "fy"], keep=False)]
    if len(dup):
        report["gaps"].append(f"duplicate 10-Ks for same firm-year, kept latest filing: "
                              f"{dup[['ticker', 'fy', 'accession']].to_dict('records')}")
        m = m.sort_values("filing_date").drop_duplicates(["ticker", "fy"], keep="last")

    # Missing firm-years. If the last configured year is missing for any firm,
    # drop it for every firm (README T1 rule).
    have = set(zip(m["ticker"], m["fy"]))
    missing = [(f.ticker, y) for f in cfg.firms for y in years if (f.ticker, y) not in have]
    last = years[-1]
    lacking_last = [t for t, y in missing if y == last]
    effective_years = years
    if lacking_last:
        effective_years = years[:-1]
        msg = (f"FY{last} 10-K missing for {lacking_last}; FY{last} dropped for every firm")
        log.warning(msg)
        report["gaps"].append(msg)
        m = m[m["fy"] != last]
    for t, y in missing:
        if y != last or not lacking_last:
            report["gaps"].append(f"missing 10-K: {t} FY{y}")

    m = m.sort_values(["ticker", "fy"]).reset_index(drop=True)
    p.manifest.parent.mkdir(parents=True, exist_ok=True)
    m.to_csv(p.manifest, index=False)

    # ---- check
    expected = len(cfg.firms) * len(effective_years)
    per_firm = m.groupby("ticker").size().to_dict()
    report.update({
        "rows": len(m), "expected_rows": len(cfg.firms) * len(years),
        "effective_fiscal_years": effective_years, "per_firm": per_firm,
        "name_mismatches": name_mismatch, "all_form_10k": bool((m["form"] == "10-K").all()),
        "missing_firm_years": missing,
    })
    write_report(cfg, "download", report)
    print(f"\n[T1 check] manifest rows: {len(m)} (expected {expected}); per firm: {per_firm}")
    print(f"[T1 check] all form == 10-K: {report['all_form_10k']}")
    print(f"[T1 check] header names match config: {not name_mismatch} {name_mismatch or ''}")
    print(f"[T1 check] 10-K/A dropped: {len(report.get('amendments_dropped', []))}, "
          f"10-KT flagged: {len(report.get('transition_reports_flagged', []))}")
    if missing:
        print(f"[T1 check] missing firm-years: {missing}")
    from pilot.cli import CheckFailed
    if name_mismatch:
        raise CheckFailed(f"company name mismatch: {name_mismatch}")
    if not report["all_form_10k"] or len(m) > len(cfg.firms) * len(years):
        raise CheckFailed("manifest contains non-10-K rows or too many rows")
    return m


def load_manifest(cfg: Config) -> pd.DataFrame:
    m = pd.read_csv(cfg.paths.manifest, dtype={"cik": str})
    for c in ("period_of_report", "filing_date"):
        m[c] = pd.to_datetime(m[c]).dt.date
    return m
