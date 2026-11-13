"""One command for the whole pipeline:  python3 run.py

Sets up the virtualenv on the first run, asks once for the SEC identity (saved to .env),
then runs download -> clean -> score -> bins -> returns -> plot -> export -> coverage.
Extra arguments go to `python -m pilot all`, e.g.  python3 run.py --refresh
Run a single step instead with  python3 run.py clean   (any `python -m pilot` step).
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
STEPS = {"download", "clean", "score", "bins", "returns", "plot", "export", "coverage", "diff", "all"}


def run(cmd, **kw):
    subprocess.run([str(c) for c in cmd], cwd=ROOT, check=True, **kw)


def setup():
    if sys.version_info < (3, 11):
        sys.exit(f"Python 3.11 or newer is required (this is {sys.version.split()[0]}).")
    if not PY.exists():
        print("Creating .venv ...")
        run([sys.executable, "-m", "venv", VENV])
    ready = VENV / ".installed"
    if not ready.exists() or ready.stat().st_mtime < (ROOT / "pyproject.toml").stat().st_mtime:
        print("Installing dependencies (first run only) ...")
        run([PY, "-m", "pip", "install", "-q", "--upgrade", "pip"])
        run([PY, "-m", "pip", "install", "-q", "-e", ".[dev]"])
        ready.touch()


def sec_identity():
    """The SEC asks every downloader to declare a name and email. Read .env, else ask once."""
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            key, sep, val = line.partition("=")
            if sep and key.strip() in ("SEC_USER_NAME", "SEC_USER_EMAIL"):
                os.environ.setdefault(key.strip(), val.strip().strip("\"'"))
    if os.environ.get("SEC_USER_NAME") and os.environ.get("SEC_USER_EMAIL"):
        return
    print("The SEC requires a name and email on downloads (kept only in your local .env file).")
    name = input("Your name: ").strip()
    email = input("Your email: ").strip()
    if not name or not email:
        sys.exit("Name and email are both required.")
    env_file.write_text(f"SEC_USER_NAME={name}\nSEC_USER_EMAIL={email}\n")
    os.environ["SEC_USER_NAME"], os.environ["SEC_USER_EMAIL"] = name, email


def main():
    args = sys.argv[1:]
    step_args = args if args and args[0] in STEPS else ["all", *args]
    setup()
    sec_identity()
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    cmds = [["score"], ["bins"]] if step_args == ["score"] else [step_args]
    for c in cmds:
        run([PY, "-m", "pilot", *c], env=env)
    print("\nDone. Figures are in outputs/figures/, the coverage report is outputs/coverage.txt.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
