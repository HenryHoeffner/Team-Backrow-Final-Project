# Lazy Prices pilot. Each target is one task from the README build plan.
# Uses the project virtualenv when it exists, otherwise python3 on PATH.
PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
export PYTHONPATH := src
PILOT := $(PYTHON) -m pilot

.PHONY: setup download clean score returns plot coverage diffs all test reset

setup:            ## create .venv and install dependencies
	python3 -m venv .venv
	.venv/bin/pip install -q --upgrade pip
	.venv/bin/pip install -q -e ".[dev]"

download:         ## T1: fetch 10-Ks from EDGAR, write data/filings_manifest.csv
	$(PILOT) download

clean:            ## T2: extract the 10-K document and write data/clean/*.txt
	$(PILOT) clean

score:            ## T3 + T4: similarity vs prior year, then within-year bins
	$(PILOT) score
	$(PILOT) bins

returns:          ## T5: 12-month firm and SPY returns after each filing
	$(PILOT) returns

plot:             ## T6: one PNG per firm in outputs/figures/
	$(PILOT) plot

coverage:         ## T7: outputs/coverage.txt
	$(PILOT) coverage

diffs:            ## T8 (stretch): sentence diffs for the three lowest-similarity filings
	$(PILOT) diff --lowest 3

all: download clean score returns plot coverage

test:
	$(PYTHON) -m pytest -q

reset:            ## delete generated data and outputs (downloads included)
	rm -rf data outputs
