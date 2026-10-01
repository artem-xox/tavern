.DEFAULT_GOAL := help
.PHONY: help install run test check build benchmark

help:
	@printf 'make run      Start the backend and browser client; Ctrl+C stops both\n'
	@printf 'make install  Install Python and frontend dependencies\n'
	@printf 'make test     Run backend tests\n'
	@printf 'make check    Run backend tests and TypeScript checks\n'
	@printf 'make build    Build the browser client\n'
	@printf 'make benchmark Measure one NPC minute using real Jev requests\n'

install:
	@test -x .venv/bin/python || uv venv .venv
	uv pip install --python .venv/bin/python -e '.[dev]'
	npm --prefix frontend ci

run:
	@python3 scripts/run.py

test:
	.venv/bin/python -m pytest

check: test
	npm --prefix frontend run check

build:
	npm --prefix frontend run build

benchmark:
	.venv/bin/python scripts/benchmark_cost.py
