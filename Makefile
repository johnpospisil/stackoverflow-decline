# Stack Overflow decline: pipeline entry points.
# Paths: override with SOD_RAW_DIR / SOD_DATA_DIR (see src/sod/config.py).

PY := uv run python -I

.PHONY: all check-env ingest ingest-posts ingest-tables ingest-posthistory progress build build-questions build-cohorts build-panels eda models models-its models-forecast models-synth models-robustness models-tags models-thin-data figures report test lint clean-processed

all: check-env ingest build models figures report

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

models: models-its models-forecast models-synth models-robustness models-tags models-thin-data

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

figures:
	@echo "figures: not yet implemented (P26-P27)"

report:
	@echo "report: not yet implemented (P30)"

test:
	uv run pytest -q

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

# Deletes derived data only; raw XML in SOD_RAW_DIR is never touched.
clean-processed:
	@test -n "$$SOD_DATA_DIR" || (echo "set SOD_DATA_DIR explicitly to clean"; exit 1)
	rm -rf "$$SOD_DATA_DIR/parquet" "$$SOD_DATA_DIR/panels" "$$SOD_DATA_DIR/models" "$$SOD_DATA_DIR/sod.duckdb"
