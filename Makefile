# itibar — buckets 1 and 2, PR 5, PR 6, PR 7. Every target is reproducible from an empty checkout
# (`make lists-fetch` re-downloads the classical list text from Shamela; its output is committed).
# Paths can be redirected with ITIBAR_DATA_DIR / ITIBAR_PARQUET_DIR / ITIBAR_OUT_DIR
# (see src/itibar/paths.py); `make ci` uses that to run on the committed fixture.

UV      ?= uv
PY      := $(UV) run python
PYTEST  := $(UV) run pytest
FIXTURE := tests/fixture/parquet
CI_OUT  ?= .ci-out


.PHONY: translate translate-pending translate-import translate-status translate-sample translate-checks hadeethenc hadeethenc-fetch
.PHONY: all setup data book-compilers audit words matn bundles stages narrators lists lists-fetch mudallisin mudallisin-fetch provenance-fetch conditional conditional-fetch residue residue-fetch source-template verdicts shahid-inspection chapters pools gold gates test figures fixture ci site site-check site-fixture render-gold clean

all: data conditional bundles stages source-template verdicts audit narrators lists chapters pools residue gold figures

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
	$(PY) -m itibar.unnamed

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

## make conditional: conditional narrator rulings from lists/source/ -> lists/conditional*.{yaml,csv} (PR 6 §2)
conditional:
	$(PY) -m itibar.conditional build

## make conditional-fetch: re-download the Taqrib/Tahrir entries of the seed and the ikhtilat books (Shamela)
conditional-fetch:
	$(PY) -m itibar.conditional fetch-kawakib
	$(PY) -m itibar.conditional fetch-books
	$(PY) -m itibar.conditional fetch-taqrib
	$(PY) -m itibar.conditional refresh-tahrir

## make residue: reports/residue.md + figures/fig6_residue.* from out/records.parquet (PR 6 §3)
residue:
	$(PY) -m itibar.residue report

## make residue-fetch: Taqrib/Tahrir verdicts of the narrators most often weakest at the sahih/hasan line
residue-fetch:
	$(PY) -m itibar.residue fetch

## make source-template: the source's grade decoded (sanads.hukum templates, reproduction, the group rule)
##   -> out/source_template.parquet, reports/source_grade.md, reports/source_templates.csv (PR 7 §1-2)
source-template:
	$(PY) -m itibar.source_template all

## make verdicts: the critics' own verdicts extracted and scored -> out/verdicts.parquet, out/critics/,
##   reports/verdicts.md, reports/verdicts_survey.csv, figures/fig7_critics.* (PR 7 §4-5)
verdicts:
	$(PY) -m itibar.verdicts survey
	$(PY) -m itibar.verdicts extract
	$(PY) -m itibar.critics all

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
	ITIBAR_PARQUET_DIR=$(CURDIR)/$(FIXTURE) ITIBAR_OUT_DIR=$(CURDIR)/$(CI_OUT) $(PY) -m itibar.unnamed
	ITIBAR_PARQUET_DIR=$(CURDIR)/$(FIXTURE) ITIBAR_OUT_DIR=$(CURDIR)/$(CI_OUT) $(PY) -m itibar.matn
	ITIBAR_PARQUET_DIR=$(CURDIR)/$(FIXTURE) ITIBAR_OUT_DIR=$(CURDIR)/$(CI_OUT) $(PY) -m itibar.pipeline
	ITIBAR_PARQUET_DIR=$(CURDIR)/$(FIXTURE) ITIBAR_OUT_DIR=$(CURDIR)/$(CI_OUT) $(PY) -m itibar.verdicts extract
	ITIBAR_PARQUET_DIR=$(CURDIR)/$(FIXTURE) ITIBAR_OUT_DIR=$(CURDIR)/$(CI_OUT) $(PYTEST) -q

## The English layer (DECISIONS D102). translations/<kind>.parquet is the contract; any producer writes it
## through `import`, which checks every item against the current Arabic source.
## make translate-pending OUT=dir [FIXTURE=1]: the missing or stale items as JSONL work sets for a session
translate-pending:
	$(PY) -m itibar.translate pending --out $(or $(OUT),translations/pending) $(if $(FIXTURE),--fixture,)

## make translate-import FILES="dir/*.jsonl" PRODUCER=session:YYYY-MM-DD:label [MODEL=...]
translate-import:
	$(PY) -m itibar.translate import $(FILES) --producer $(PRODUCER) $(if $(MODEL),--model $(MODEL),) $(if $(FIXTURE),--fixture,)

translate-status:
	$(PY) -m itibar.translate status $(if $(FIXTURE),--fixture,)

## make translate: the optional Message Batches path (needs `uv sync --extra translate` and API credentials)
translate:
	$(UV) run --extra translate python -m itibar.translate api $(if $(FIXTURE),--fixture,)

## make translate-sample / translate-checks: the second pass on 200 random items (translations/checks.parquet)
translate-sample:
	$(PY) -m itibar.translate sample --n 200 --out $(or $(OUT),translations/check-sample.jsonl)

translate-checks:
	$(PY) -m itibar.translate record-checks $(FILE) --checker $(CHECKER)

## make hadeethenc-fetch: HadeethEnc's English items (API v1) -> translations/source/hadeethenc_en.jsonl (slow, polite)
hadeethenc-fetch:
	$(PY) -m itibar.hadeethenc fetch

## make hadeethenc: join them to the groups -> translations/hadeethenc.parquet (no network)
hadeethenc:
	$(PY) -m itibar.hadeethenc build

## make site: build the static reader from existing pipeline outputs
site:
	$(PY) -m itibar.site

site-check:
	$(PY) -m itibar.site --check

## make site-fixture: use the Parquet outputs from make ci
site-fixture:
	ITIBAR_PARQUET_DIR=$(CURDIR)/$(FIXTURE) ITIBAR_OUT_DIR=$(abspath $(CI_OUT)) $(PY) -c 'from itibar.narrators import build; build()'
	ITIBAR_PARQUET_DIR=$(CURDIR)/$(FIXTURE) ITIBAR_OUT_DIR=$(abspath $(CI_OUT)) $(PY) -m itibar.site --dest $(CI_OUT)/site
	$(PY) -m itibar.site --check --dest $(CI_OUT)/site

render-gold:
	for g in 319 276 397 2852 1581; do $(UV) run itibar render $$g; done

clean:
	rm -rf out $(CI_OUT) .pytest_cache
