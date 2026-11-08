.DEFAULT_GOAL := help
.PHONY: help install run test check build evening eval golden

SEED ?= 0
CAST ?= locals
MODE ?=
OUT ?= runs/evening-$(SEED)
CALLS ?=
PLAYER ?=
SCENARIO ?=
LIMIT ?= 1200
TRACE ?=
SEEDS ?= 1
ENV ?= .env
GOLDEN ?= runs/golden

help:
	@printf 'make run      Start the backend and browser client; Ctrl+C stops both\n'
	@printf '              TRACE=true traces Jev and Haiku calls to LangSmith (LANGSMITH_API_KEY in .env)\n'
	@printf 'make install  Install Python and frontend dependencies\n'
	@printf 'make test     Run backend tests\n'
	@printf 'make check    Run backend tests, mypy and TypeScript checks\n'
	@printf 'make build    Build the browser client\n'
	@printf 'make evening  Play a headless evening; writes events.jsonl, metrics.json (+ calls.jsonl live) to OUT\n'
	@printf '              CAST=locals|guests SEED=0 OUT=runs/evening-SEED LIMIT=1200 game seconds\n'
	@printf '              MODE=live (default when .env has TYPESAFE_API_KEY), local, or replay CALLS=path/calls.jsonl\n'
	@printf '              (a replay needs the SEED, LIMIT and .env AI settings of the recorded run)\n'
	@printf '              TRACE=true traces live calls to LangSmith, one thread per character\n'
	@printf 'make eval     Local only: play the dialogue eval scenarios live (Jev + Haiku), measure and judge a minute\n'
	@printf '              of talk; writes runs/evals/<time>/report.md. SEEDS="1 2" ENV=path/.env\n'
	@printf '              PLAYER=data/players/monroe_meddles.json SCENARIO=data/scenarios/monroe_night.json puts that guest at the wheel\n'
	@printf 'make golden   Play five offline evenings (locals, guests × seeds 1, 5, then Monroe at the wheel) into GOLDEN=runs/golden, to diff before and after a refactor\n'

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
	npm --prefix frontend test

build:
	npm --prefix frontend run build

evening:
	.venv/bin/python scripts/evening.py --cast $(CAST) --seed $(SEED) --out $(OUT) --time-limit $(LIMIT) \
		$(if $(MODE),--mode $(MODE)) $(if $(CALLS),--calls $(CALLS)) $(if $(SCENARIO),--scenario $(SCENARIO)) $(if $(PLAYER),--player-script $(PLAYER)) $(if $(filter true,$(TRACE)),--trace)

eval:
	PYTHONPATH=backend .venv/bin/python scripts/dialogue_eval.py --seeds $(SEEDS) --env-file $(ENV)

golden:
	@for cast in locals guests; do for seed in 1 5; do \
		PYTHONPATH=backend .venv/bin/python scripts/evening.py --cast $$cast --seed $$seed --mode local --writer scripted \
			--no-retelling --env-file /dev/null --out $(GOLDEN)/$$cast-$$seed \
			> $(GOLDEN)-$$cast-$$seed.log 2>&1 || { cat $(GOLDEN)-$$cast-$$seed.log; exit 1; }; \
	done; done
	@PYTHONPATH=backend .venv/bin/python scripts/evening.py --cast guests --scenario data/scenarios/monroe_night.json \
		--player-script data/players/monroe_meddles.json --seed 5 --mode local --writer scripted \
		--no-retelling --env-file /dev/null --out $(GOLDEN)/monroe-5 \
		> $(GOLDEN)-monroe-5.log 2>&1 || { cat $(GOLDEN)-monroe-5.log; exit 1; }
