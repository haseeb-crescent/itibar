# itibar — buckets 1 and 2, PR 5. Every target is reproducible from an empty checkout
# (`make lists-fetch` re-downloads the classical list text from Shamela; its output is committed).
# Paths can be redirected with ITIBAR_DATA_DIR / ITIBAR_PARQUET_DIR / ITIBAR_OUT_DIR
# (see src/itibar/paths.py); `make ci` uses that to run on the committed fixture.

UV      ?= uv
PY      := $(UV) run python
PYTEST  := $(UV) run pytest
FIXTURE := tests/fixture/parquet
CI_OUT  ?= .ci-out

.PHONY: all setup data book-compilers audit words matn bundles stages narrators lists lists-fetch mudallisin mudallisin-fetch provenance-fetch shahid-inspection chapters pools gold gates test figures fixture ci render-gold clean

all: data bundles stages audit narrators lists chapters pools gold figures

setup:
	$(UV) sync

## make data: download hadith-kg.db (pinned revision, sha256-verified) and convert to Parquet/DuckDB
data: setup
	$(PY) -m itibar.data

## make book-compilers: recompute the derived book_compilers table (book transmitters) without reconverting
book-compilers:
	$(PY) -c "from itibar import load; load.write_book_compilers()"

## make audit: re-verify upstream facts, write reports/audit.md (regenerates config/grades.yaml labels)
audit:
	$(PY) -m itibar.audit

words:
	$(PY) -m itibar.words

## make matn: normalized matn tokens and idf for the shahid overlap -> out/matn_tokens.parquet, out/matn_vocab.parquet
matn:
	$(PY) -m itibar.matn

## make bundles: B(g) for every meaning group -> out/bundles/, out/records.parquet, out/chains.parquet
bundles: words matn
	$(PY) -m itibar.pipeline

## make stages: the PR 5 corrections applied cumulatively (config/stages/) -> out/stages/ (audit section 11.1)
stages:
	$(PY) -m itibar.stages

## make narrators: narrator census (out/narrators.parquet) + reports/common_links.md + fig4
narrators:
	$(PY) -m itibar.narrators

## make lists: parse lists/source -> lists/*.yaml, match to groups, bin -> reports/lists.md + fig3
lists:
	$(PY) -m itibar.lists all

lists-fetch:
	$(PY) -m itibar.lists fetch

## make mudallisin: parse Tabaqat al-Mudallisin and match it to rawis -> lists/mudallisin*.{yaml,csv}
mudallisin:
	$(PY) -m itibar.mudallisin all

mudallisin-fetch:
	$(PY) -m itibar.mudallisin fetch

## make provenance-fetch: the 40-narrator sample against the Taqrib and Tahrir (Shamela) -> lists/source/taqrib_sample.jsonl
provenance-fetch:
	$(PY) -m itibar.provenance fetch

## make shahid-inspection: reports/shahid_inspection.md from lists/shahid_inspection.yaml
shahid-inspection:
	$(PY) -m itibar.siblings inspect

## make chapters: chapter census over the topic tree -> reports/chapters.md + fig5
chapters:
	$(PY) -m itibar.chapters

## make pools: the two pooled-bundle case studies (topic subtrees) -> reports/pools/
pools:
	$(UV) run itibar pool --topic 28754 --save reports/pools/mahdi
	$(UV) run itibar pool --topic 28661 --save reports/pools/dajjal

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
	ITIBAR_PARQUET_DIR=$(CURDIR)/$(FIXTURE) ITIBAR_OUT_DIR=$(CURDIR)/$(CI_OUT) $(PY) -m itibar.matn
	ITIBAR_PARQUET_DIR=$(CURDIR)/$(FIXTURE) ITIBAR_OUT_DIR=$(CURDIR)/$(CI_OUT) $(PY) -m itibar.pipeline
	ITIBAR_PARQUET_DIR=$(CURDIR)/$(FIXTURE) ITIBAR_OUT_DIR=$(CURDIR)/$(CI_OUT) $(PYTEST) -q

render-gold:
	for g in 319 276 397 2852 1581; do $(UV) run itibar render $$g; done

clean:
	rm -rf out $(CI_OUT) .pytest_cache
