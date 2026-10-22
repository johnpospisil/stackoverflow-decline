# Stack Overflow decline: pipeline entry points.
# Paths: override with SOD_RAW_DIR / SOD_DATA_DIR (see src/sod/config.py).

PY := uv run python -I

# Ignore any other active virtualenv (e.g. ~/tf): uv always uses this project's .venv.
unexport VIRTUAL_ENV

# `make all SAMPLE=1`: the whole pipeline on a small synthetic dump (sod.sample) in .sample/,
# with fewer MCMC draws and bootstrap replicates. Never touches the real data or report/.
ifeq ($(SAMPLE),1)
SAMPLE_DIR ?= $(CURDIR)/.sample
export SOD_SAMPLE := 1
export SOD_RAW_DIR := $(SAMPLE_DIR)/raw
export SOD_DATA_DIR := $(SAMPLE_DIR)/data
export SOD_REFERENCE_DIR := $(SAMPLE_DIR)/reference
export SOD_REPORT_DIR := $(SAMPLE_DIR)/report
endif

.PHONY: all app serve-app sample-data check-env ingest ingest-posts ingest-tables ingest-posthistory progress build build-questions build-cohorts build-panels eda models models-its models-forecast models-synth models-robustness models-tags models-thin-data models-question-mix models-newcomers models-answerers models-responsiveness models-github models-validation figures report test lint clean-processed

all: $(if $(filter 1,$(SAMPLE)),sample-data) check-env ingest build models figures app report

# Synthetic dump for SAMPLE=1 (fresh each time; deterministic)
sample-data:
	@test "$(SAMPLE)" = 1 || (echo "sample-data needs SAMPLE=1"; exit 1)
	rm -rf "$(SAMPLE_DIR)/data"
	$(PY) -m sod.sample

check-env:
	$(PY) -m sod.check_env

ingest: check-env ingest-posts ingest-tables ingest-posthistory

ingest-posts: check-env
	$(PY) -m sod.ingest.posts

ingest-tables: check-env
	$(PY) -m sod.ingest.tables

ingest-posthistory: check-env
	$(PY) -m sod.ingest.posthistory

# Live progress for running jobs (any terminal): one overall line.
# JOB=tables to pick a job; DETAIL=1 to list every task.
progress:
	@$(PY) -m sod.progress $(JOB) $(if $(DETAIL),--detail,)

build: build-questions build-tags build-cohorts build-panels

build-tags:
	$(PY) -m sod.build.tag_taxonomy

build-cohorts:
	$(PY) -m sod.build.cohorts

build-panels:
	$(PY) -m sod.build.panels

build-questions:
	$(PY) -m sod.build.questions

# P14: descriptive charts + report/qa/eda_summary.json; re-executes the notebook.
eda:
	uv run jupyter nbconvert --to notebook --execute --inplace notebooks/01_eda.ipynb

models: models-its models-forecast models-synth models-robustness models-tags models-thin-data models-question-mix models-newcomers models-answerers models-responsiveness models-github models-validation

# P15: interrupted time series (weekly Stack Overflow)
models-its:
	$(PY) -m sod.models.its

# P16: ETS and Prophet forecast counterfactuals + backtest
models-forecast:
	$(PY) -m sod.models.forecast

# P17: synthetic control (primary), placebos, sensitivity, DiD vs ru, platform-wide test
models-synth:
	$(PY) -m sod.models.synth

# P18: pre-registered robustness checks + forest plot (needs P15-P17 outputs)
models-robustness:
	$(PY) -m sod.models.robustness

# P19: hierarchical negative binomial tag model (about 10 min; `make progress`)
models-tags:
	$(PY) -m sod.models.tags

# P20: H2 test (age slope; post-2021 tags vs lifecycle benchmark); needs models-tags
models-thin-data:
	$(PY) -m sod.models.thin_data

# P21: H3 question mix, 2021 vs 2025 (tag-mix reweighting, bootstrap, Lee bounds)
models-question-mix:
	$(PY) -m sod.models.question_mix

# P22: H4 newcomers (synthetic control on first-time share; Kaplan-Meier return)
models-newcomers:
	$(PY) -m sod.models.newcomers

# P23: H5 answerers (placebo cohorts), core activity, emerging top answerers
models-answerers:
	$(PY) -m sod.models.answerers

# P24: responsiveness (exploratory E1)
models-responsiveness:
	$(PY) -m sod.models.responsiveness

# P25: GitHub issue activity vs SO tags (uses the cached GH Archive extract; --refresh re-queries BigQuery)
models-github:
	$(PY) -m sod.models.github

# P29: validation numbers (questions-not-asked range, Holm across H2-H5, leakage checks)
models-validation:
	$(PY) -m sod.models.validation

figures:
	$(PY) -m sod.viz.hero
	$(PY) -m sod.viz.figures

# P31: tag lookup app data (app/data/tags.json; the page is app/index.html). Preview:
# `make serve-app`, then open http://localhost:8031/#tag=python
app:
	$(PY) -m sod.app_data

serve-app:
	cd app && $(PY) -m http.server 8031

# P30: the article (report/index.html, self-contained). Numbers come from report/qa via sod.article.
QUARTO ?= $(shell command -v quarto 2>/dev/null || echo $(HOME)/opt/quarto-1.10.19/bin/quarto)
# With SAMPLE=1 the article is rendered from a copy in .sample/report (sample numbers and
# figures), so the real report/index.html is never overwritten.
report:
ifeq ($(SAMPLE),1)
	cp report/index.qmd report/references.bib report/article.css "$(SOD_REPORT_DIR)/"
	QUARTO_PYTHON=$(CURDIR)/.venv/bin/python $(QUARTO) render "$(SOD_REPORT_DIR)/index.qmd"
else
	QUARTO_PYTHON=$(CURDIR)/.venv/bin/python $(QUARTO) render report/index.qmd
endif

test:
	uv run pytest -q

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

# Deletes derived data only; raw XML in SOD_RAW_DIR is never touched.
clean-processed:
	@test -n "$$SOD_DATA_DIR" || (echo "set SOD_DATA_DIR explicitly to clean"; exit 1)
	rm -rf "$$SOD_DATA_DIR/parquet" "$$SOD_DATA_DIR/panels" "$$SOD_DATA_DIR/models" "$$SOD_DATA_DIR/sod.duckdb"
