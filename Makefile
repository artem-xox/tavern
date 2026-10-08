.DEFAULT_GOAL := help
.PHONY: help install run test check build benchmark evening

SEED ?= 0
MODE ?=
OUT ?= runs/evening-$(SEED)
CALLS ?=
LIMIT ?= 1200
TRACE ?=

help:
	@printf 'make run      Start the backend and browser client; Ctrl+C stops both\n'
	@printf '              TRACE=true traces Jev and Haiku calls to LangSmith (LANGSMITH_API_KEY in .env)\n'
	@printf 'make install  Install Python and frontend dependencies\n'
	@printf 'make test     Run backend tests\n'
	@printf 'make check    Run backend tests, mypy and TypeScript checks\n'
	@printf 'make build    Build the browser client\n'
	@printf 'make benchmark Measure one NPC minute using real Jev requests\n'
	@printf 'make evening  Play a headless evening; writes events.jsonl, metrics.json (+ calls.jsonl live) to OUT\n'
	@printf '              SEED=0 OUT=runs/evening-SEED LIMIT=1200 game seconds\n'
	@printf '              MODE=live (default when .env has TYPESAFE_API_KEY), local, or replay CALLS=path/calls.jsonl\n'
	@printf '              (a replay needs the SEED, LIMIT and .env AI settings of the recorded run)\n'
	@printf '              TRACE=true traces live calls to LangSmith, one thread per character\n'

install:
	@test -x .venv/bin/python || uv venv .venv
	uv pip install --python .venv/bin/python -e '.[dev]'
	npm --prefix frontend ci

# Traces spend LangSmith quota, so only TRACE=true switches them on; .env cannot.
run:
	@TAVERN_TRACE=$(TRACE) python3 scripts/run.py

test:
	.venv/bin/python -m pytest

check: test
	.venv/bin/mypy
	npm --prefix frontend run check

build:
	npm --prefix frontend run build

benchmark:
	.venv/bin/python scripts/benchmark_cost.py

evening:
	.venv/bin/python scripts/evening.py --seed $(SEED) --out $(OUT) --time-limit $(LIMIT) \
		$(if $(MODE),--mode $(MODE)) $(if $(CALLS),--calls $(CALLS)) $(if $(filter true,$(TRACE)),--trace)
