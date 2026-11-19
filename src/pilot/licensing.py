"""Keep licensed CRSP/WRDS data out of git.

The repo is public, so anything committed is published. CRSP data is licensed to Lehigh users
and stays in git-ignored files in data/ (see README_DATA.md). Results computed from it, such as
bin averages, test statistics and the coverage report, may be committed.

This module checks every file git tracks (committed or staged) and reports:
  - a file that must never be tracked: the CRSP extracts and the price/return series built from
    them (data/prices_monthly.csv, data/prices_monthly.source.txt, data/returns.parquet);
  - a data file whose name mentions CRSP or WRDS;
  - a parquet or CSV file with CRSP-only columns (permno, ret_adj, dlret, vwretd, ...) or
    price/return-series columns (adj_close, prc, ret).

It cannot recognize CRSP numbers saved under other column names, so code that reads CRSP must
write its output to git-ignored files.

Run it with `make check-data`; the git pre-commit hook (`make hooks`) runs it before every commit.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

MARKERS = ("crsp", "wrds")

NEVER_TRACK = {"data/prices_monthly.csv", "data/prices_monthly.source.txt", "data/returns.parquet"}

# Columns that exist only in CRSP extracts.
CRSP_COLUMNS = {
    "permno", "permco", "ncusip", "shrcd", "exchcd", "prc_raw", "altprc", "bidlo", "askhi",
    "cfacpr", "cfacshr", "ret_adj", "retx", "dlret", "dlretx", "dlret_filled", "dlret_shumway",
    "dlstcd", "dlstdt", "vwretd", "vwretx", "ewretd", "ewretx", "sprtrn", "totval", "totcnt",
    "usdval", "usdcnt",
}
# Columns of a price or return series (raw data, not a result).
SERIES_COLUMNS = {"adj_close", "prc", "ret", "price", "close"}

DATA_DIRS = ("data/", "app_data/", "outputs/")
TABLE_SUFFIXES = {".parquet", ".csv"}
DATA_SUFFIXES = TABLE_SUFFIXES | {".dta", ".sas7bdat", ".feather", ".pkl", ".pickle", ".xlsx",
                                  ".xls", ".h5", ".json", ".txt"}


def tracked_files(root: Path) -> list[str] | None:
    """Files in git's index (committed or staged), or None when git is unavailable."""
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return [p for p in out.stdout.decode().split("\0") if p]


def is_data_file(path: str) -> bool:
    """Code and docs may mention CRSP; only data files are checked."""
    suffix = Path(path).suffix.lower()
    if suffix in DATA_SUFFIXES - {".json", ".txt"}:
        return True
    return path.startswith(DATA_DIRS) and suffix in DATA_SUFFIXES


def _columns(file: Path) -> list[str]:
    if file.suffix.lower() == ".parquet":
        import pyarrow.parquet as pq
        return list(pq.read_schema(file).names)
    with file.open(encoding="utf-8", errors="replace") as f:
        return [c.strip().strip('"') for c in f.readline().split(",")]


def problems_in(file: Path, rel: str) -> list[str]:
    found = []
    if rel in NEVER_TRACK:
        found.append(f"{rel}: built from CRSP; it must stay git-ignored")
    if any(m in Path(rel).name.lower() for m in MARKERS):
        found.append(f"{rel}: file name mentions CRSP/WRDS")
    if file.suffix.lower() in TABLE_SUFFIXES and file.exists():  # absent = staged for deletion
        try:
            cols = {c.lower() for c in _columns(file)}
        except Exception as e:  # report an unreadable table rather than pass it
            return found + [f"{rel}: could not read columns ({e})"]
        if bad := sorted(CRSP_COLUMNS & cols):
            found.append(f"{rel}: CRSP columns {bad}")
        if bad := sorted(SERIES_COLUMNS & cols):
            found.append(f"{rel}: price/return series columns {bad}")
    return found


def find_problems(root: Path) -> list[str] | None:
    """Every licensed-data problem in tracked files, or None when git is unavailable."""
    paths = tracked_files(root)
    if paths is None:
        return None
    return [msg for rel in paths if is_data_file(rel) for msg in problems_in(root / rel, rel)]


def main() -> int:
    from pilot.config import PROJECT_ROOT

    found = find_problems(PROJECT_ROOT)
    if found is None:
        print("[check-data] git not available; skipped")
        return 0
    if found:
        print("[check-data] Licensed CRSP data would be published in this PUBLIC repo:")
        for msg in found:
            print(f"  - {msg}")
        print("Unstage it (git restore --staged <file>) and keep it in git-ignored files.\n"
              "See README_DATA.md. If this is a false alarm, ask the team before overriding.")
        return 1
    print("[check-data] no CRSP data in tracked files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
