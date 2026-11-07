---
id: S3-R00
title: Record golden evenings that every refactor is checked against
status: done
needs: []
touches: [Makefile]
---

# S3-R00 — Golden evenings

## Why

The R series changes no behavior unless a task says so. The proof is an offline evening that replays
byte for byte: the local policy and the scripted writer are deterministic per seed (checked 2026-11-07:
guests, seed 5, two runs, identical `events.jsonl` and `metrics.json`, about 6 s each). Today that check is a
long command typed by hand. This task makes it one target and records the baseline every later R task
compares with.

## Scope

- In: a `make golden` target that plays the checkout's own code, also from a git worktree (`runs/` is
  gitignored, so a baseline is never committed: every lane records its own, see "The check" below).
- Out: any change under `backend/`, `tests/`, `frontend/` or `scripts/`.

## Shape

In `Makefile`:

```make
GOLDEN ?= runs/golden

golden:
	@for cast in locals guests; do for seed in 1 5; do \
		PYTHONPATH=backend .venv/bin/python scripts/evening.py --cast $$cast --seed $$seed --mode local --writer scripted \
			--no-retelling --env-file /dev/null --out $(GOLDEN)/$$cast-$$seed \
			> $(GOLDEN)-$$cast-$$seed.log 2>&1 || { cat $(GOLDEN)-$$cast-$$seed.log; exit 1; }; \
	done; done
```

Add `golden` to `.PHONY` and one help line: `make golden   Play four offline evenings (locals, guests ×
seeds 1, 5) into GOLDEN=runs/golden, to diff before and after a refactor`.

The logs sit beside the directory, not in it, because they hold wall-clock seconds.

`PYTHONPATH=backend` matters: the editable install points at the main checkout, so in a git worktree a bare
`.venv/bin/python scripts/evening.py` silently plays **main's** code and every diff would come out empty.

## Steps

1. Add the target and its help line. — check:
   ```bash
   make golden GOLDEN=runs/golden-a
   make golden GOLDEN=runs/golden-b
   diff -r runs/golden-a runs/golden-b
   ```
   prints nothing, and each of the 4 directories holds `events.jsonl` and `metrics.json`.
2. Prove the worktree case, from any git worktree of the series branch:
   `PYTHONPATH=backend .venv/bin/python -c "import tavern; print(tavern.__file__)"` prints the worktree's
   own `backend/tavern/__init__.py`; without `PYTHONPATH` it prints the main checkout's. Note both in Results.

## The check every later R task runs

Each lane records its own base **before its first change**, from the commit it branched from, then compares:

```bash
make golden GOLDEN=runs/golden-base    # once, before the first edit
make golden GOLDEN=runs/golden-now     # after each step
diff -r runs/golden-base runs/golden-now
```

Empty output means no behavior change. A task allowed to change the log names the files and fields that
may differ, and compares later steps of its own against the output of its behavior-changing step.

## Local build (not a repo change)

On the owner's machine `frontend/node_modules` holds Finder duplicates (`@types/estree 2`,
`@types/trusted-types 2`, `esbuild/lib 2`, ...). `tsc` reads `estree 2` as a type library and fails, so
`npm run build` fails and with it 6 tests in `tests/test_character_action_assets.py` and
`tests/test_character_assets.py`. Before starting the series:

```bash
rm -rf frontend/node_modules
npm --prefix frontend ci
```

The duplicates come back if the project folder syncs through iCloud. After the reinstall `make check`
should be fully green (4,706 cases on 2026-11-07).

## Done when

- `make check` passes, output pasted into Results.
- Two `make golden` runs are identical.

## Results

- Added `golden` (with `GOLDEN ?= runs/golden`), its `.PHONY` entry and help line to the Makefile.
- `make golden GOLDEN=runs/golden-a` and `GOLDEN=runs/golden-b`, then `diff -r runs/golden-a runs/golden-b`: no output. Each of the 4 directories holds `events.jsonl` and `metrics.json` (plus `calls.jsonl`).
- Worktree case: with `PYTHONPATH=backend`, `tavern.__file__` is the worktree's own `backend/tavern/__init__.py`; without it, `/Users/artem.khokhlov/Desktop/playground/tavern/backend/tavern/__init__.py` (the main checkout).
- `make check`: pytest `4706 passed in 212.65s`; mypy `Success: no issues found in 133 source files`; frontend `npm test`: 271 tests, 271 pass, 0 fail.
