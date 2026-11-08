# itibar — bucket 1. Every target is reproducible from an empty checkout.
# Paths can be redirected with ITIBAR_DATA_DIR / ITIBAR_PARQUET_DIR / ITIBAR_OUT_DIR
# (see src/itibar/paths.py); `make ci` uses that to run on the committed fixture.

UV      ?= uv
PY      := $(UV) run python
PYTEST  := $(UV) run pytest
FIXTURE := tests/fixture/parquet
CI_OUT  ?= .ci-out

.PHONY: all setup data audit words bundles gold gates test figures fixture ci render-gold clean

all: data audit bundles gold figures

setup:
	$(UV) sync

## make data: download hadith-kg.db (pinned revision, sha256-verified) and convert to Parquet/DuckDB
data: setup
	$(PY) -m itibar.data

## make audit: re-verify upstream facts, write reports/audit.md (regenerates config/grades.yaml labels)
audit:
	$(PY) -m itibar.audit

words:
	$(PY) -m itibar.words

## make bundles: B(g) for every meaning group -> out/bundles/, out/records.parquet, out/chains.parquet
bundles: words
	$(PY) -m itibar.pipeline

## make gold: gold-set report (reports/gold.md) + gold tests
gold:
	$(PY) -m itibar.gold > /dev/null
	$(PYTEST) -q -m gold tests/test_gold.py

gates:
	$(PYTEST) -q -m gate tests/test_gates.py

test:
	$(PYTEST) -q -n auto

figures:
	$(PY) -m itibar.figures

## make fixture: sampled, committable Parquet subset for CI (gold + top-10 + 300 random groups)
fixture:
	$(PY) -m itibar.fixture

## make ci: the whole pipeline and test suite on the fixture (no 1.6 GB download)
ci:
	ITIBAR_PARQUET_DIR=$(CURDIR)/$(FIXTURE) ITIBAR_OUT_DIR=$(CURDIR)/$(CI_OUT) $(PY) -m itibar.words
	ITIBAR_PARQUET_DIR=$(CURDIR)/$(FIXTURE) ITIBAR_OUT_DIR=$(CURDIR)/$(CI_OUT) $(PY) -m itibar.pipeline
	ITIBAR_PARQUET_DIR=$(CURDIR)/$(FIXTURE) ITIBAR_OUT_DIR=$(CURDIR)/$(CI_OUT) $(PYTEST) -q

render-gold:
	for g in 319 276 397 2852 1581; do $(UV) run itibar render $$g; done

clean:
	rm -rf out $(CI_OUT) .pytest_cache
