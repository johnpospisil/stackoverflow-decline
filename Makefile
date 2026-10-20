# Stack Overflow decline: pipeline entry points.
# Paths: override with SOD_RAW_DIR / SOD_DATA_DIR (see src/sod/config.py).

PY := uv run python -I

.PHONY: all check-env ingest build models figures report test lint clean-processed

all: check-env ingest build models figures report

check-env:
	$(PY) -m sod.check_env

ingest: check-env
	@echo "ingest: not yet implemented (P04-P07)"

build:
	@echo "build: not yet implemented (P10-P13)"

models:
	@echo "models: not yet implemented (P15-P24)"

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
