# AGENTS.md

Shared instructions for coding agents. Keep this file tool-agnostic and short: every
line must prevent a mistake an agent would otherwise make.

## Project

The Last Inn is a sandbox game about running a border inn alongside autonomous NPCs.
Build a small prototype to test whether model-driven guests make a believable evening
that produces retellable stories. Follow `docs/DESIGN.md` and `docs/PLAN.md` (current
stage: `docs/stages/1_EVENING.md`); keep the scope small until that loop works.

## Commands

```bash
make install   # once: .venv via uv + frontend deps (asset tests build the frontend)
make run       # backend + browser client at http://127.0.0.1:5173
make test      # all backend tests
make check     # tests + frontend typecheck; CI runs this plus `make build`
make build     # frontend production build
make evening   # headless scenario evening (Jev with a .env key); SEED, MODE, OUT, LIMIT
.venv/bin/python -m pytest tests/test_navigation.py -k path -x   # one behavior, fast
```

"Done" means `make check` passes, plus `make build` if `frontend/` changed. Paste the
run. Never write "tests pass" without it.

## Workflow

Test first for everything with a Python seam: core, adapters (with fakes), HTTP.

1. Plan: if the task touches more than one file, state 2–4 steps, each with its check.
2. Red: write the smallest test for the next behavior. Run it and show it failing for
   the right reason: a behavioral assertion, not a typo or import error.
3. Green: write the least code that passes. No behavior the tests do not demand.
4. Refactor: only while green, without editing tests. If a refactor needs a test edit,
   it changed behavior: go back to step 2.
5. Bug fix: first a failing test that reproduces it, then the fix.
6. Keep refactors and behavior changes in separate commits.

`frontend/` has no unit-test runner. Keep logic out of it; verify with `make check`,
`make build`, and by running the app.

## Architecture

Functional core, imperative shell. Dependencies point inward only.

- **Core** — pure rules, no I/O: `world.py` (public API and action lifecycle),
  `activities.py` (the verb table), `room.py`, `routes.py`, `sight.py`, `memory.py`,
  `conversation.py`, `arrival.py`, `validation.py`, `navigation.py`, `briefing.py`,
  `agents.py` (candidates and decisions).
- **Adapters** — one per outside system: `jev.py` (LLM over HTTP), `persistence.py`
  (JSON files), `database.py` (PostgreSQL).
- **Shell** — `app.py`: FastAPI/WebSocket transport and sessions. The only place that
  reads the environment and wires concrete adapters (`create_default_app`).
- **Client** — `frontend/src/`: renders snapshots and sends commands.

Rules:
- Core imports only the stdlib and other core modules. Never `fastapi`, `httpx`,
  `psycopg`, `os`, an adapter, or the shell.
- Time, randomness, network, files and environment arrive as arguments (`dt`,
  `rng: Random`, `config`, `path`). No module-level `random`, `time.time()` or
  `os.environ` in core.
- A port is the smallest signature the core needs: a `Callable` alias or `Protocol` of
  1–3 functions, defined beside its consumer. Adapters conform; tests pass a fake.
- Outside data is untrusted. LLM answers, WebSocket commands and saved files are parsed
  into the documented shape at the boundary (`jev.py`, `persistence.parse_world`) and
  rejected loudly. Model output never changes the world; only validated actions do.
- Game rules live in the backend; the client never decides outcomes. A snapshot change
  means `TavernRuntime.snapshot()` and `frontend/src/types.ts` change together.
- Content is data (`data/tavern.json`). Rules key off an object's `kind`, never a
  hardcoded character or object id.
- Known leak, do not copy: `agents.py` imports `jev.py` and its tests `monkeypatch` it.
  If your task touches that seam, pass the evaluator in as an argument instead.

## Extending

- A new game system (agreements, inventory, money, cooking) is a new module named for
  the concept: pure, tested alone, wired in with one small edit. Do not grow files over
  ~400 lines (`world.py`, `app.py`, `scene.ts` today); split first, as a separate step.
- Adding a verb means one `Activity` in `activities.py` (targets, timing, preconditions,
  effects, wording, pose), plus its candidate rule and local utility in `agents.py` and its
  option sentence in `briefing.py`. The world, Jev, saves, and the client read the table.
  Do not add a new per-verb copy where one source can be imported.
- Duplicate once; abstract on the third use. No base classes, factories, registries or
  DI containers for a single implementation.

## Design rules

SOLID, applied only where it earns its keep:
- **S** — one reason to change per module. If its docstring needs "and", split it.
- **O** — extend by adding a module or table entry. If your change must add yet another
  `if kind ==` / `elif verb ==` branch (`activities.py` replaced them), say so and propose a
  table first.
- **L** — a fake behaves like the real adapter, errors included (`JevError`).
- **I** — a port exposes what the caller uses, not the provider's whole API.
- **D** — core receives collaborators as arguments; only the shell builds concrete ones.

## Navigability

- Name files, functions and tests for the domain concept (`agreements.py`, `find_path`).
  Never `utils`, `helpers`, `common`, `manager` or `base`.
- Open every module with a one-line docstring saying what it owns. Read a module's test
  file first: it is the spec.
- Anything not imported elsewhere is `_private`. No `import *`, no re-export modules, no
  string-keyed dynamic dispatch: grep must find every caller.
- Before writing a helper, grep for the concept and reuse or extend what exists.

## Coding

Python (`backend/`):
- Public functions: Google-style docstring with Args, Returns, Raises.
- Type hints on every signature; `Mapping`/`Sequence` for inputs. New domain data gets a
  `TypedDict` or frozen `dataclass`, not another `dict[str, Any]`.
- One function = one business step. More than ~15 lines or 3 distinct operations: split.
- No hidden globals. Config, constants and paths are function arguments.
- Every non-obvious assumption is a parameter or a why-comment: tie-breaks, rounding,
  iteration order, empty-input policy.
- Rounding and formatting live at the presentation layer, not in simulation or scoring.
- Fail loudly: raise `ValueError` naming the bad value. Never repair bad input silently
  (default values, dropped records, bare `except`).
- Entry points only do I/O and wiring; logic is importable and testable without files
  or network.

TypeScript (`frontend/`): no `any`; `types.ts` is the contract with the backend snapshot.

## Testing

- Never modify an existing test to make it pass. If a test looks wrong, stop and
  explain why instead of editing it. A test changes only when the user asked for the
  behavior it specifies to change; name the test and the reason before editing.
  Never delete, skip, `xfail` or weaken an assertion to get green.
- pytest only. No `unittest` classes, no assert helpers that hide the comparison.
- Use `@pytest.mark.parametrize` by default: the case list is the visible spec. Every
  case is `pytest.param(..., id="...")`; never rely on autogenerated ids.
- One parametrize block = one assertion shape. Error cases go in a separate block with
  `pytest.raises`.
- Case lists cover empty input, single element, duplicates and one malformed input,
  wherever the function takes a collection or outside data.
- Test behavior through public functions: inputs in, outputs or state change out. Not
  private helpers, call counts or internal dict layout. A test that fails under a pure
  refactor is a bad test.
- Fakes over mocks: a hand-written fake with the port's signature, or
  `httpx.MockTransport` for HTTP (`tests/test_jev.py`). New tests do not
  `monkeypatch.setattr` modules; `setenv` is fine.
- Deterministic and offline: seeded `Random`, explicit `dt`, `tmp_path`. No sleeps, no
  network, no real Jev key, no wall clock.
- Build test data with small local helpers (`common_room()` in `tests/test_social.py`),
  not 20-line inline literals.
- Run the narrowest test after every change and `make check` before finishing. Paste
  the output.

## Boundaries

- **Always**: follow the nearest existing pattern; keep `types.ts` in step with the
  snapshot.
- **Ask first**: a new dependency (pip or npm); a new top-level package or layer;
  changing the saved-world format (sessions persist in files and PostgreSQL); `.github/`
  or `.do/` deploy config; spending PixelLab credits.
- **Never**: commit secrets or `.env`; call the real Jev or network from tests; edit
  generated `frontend/dist/`; add module-level mutable state.

## Character art rule

Generate and ship only four cardinal views for tavern characters: north, south,
east, and west. Check the actual PixelLab export size before generating poses;
the standard 68 px request has returned 96 px. If a tool requires eight views
for a 68 px character, investigate a four-view route before spending credits.
See `docs/CHARACTER_ART_PIPELINE.md` for the tested workflow and current limit.

## Working principles

Bias toward caution over speed; for trivial tasks, use judgment.

- **Think before coding.** State assumptions. If several readings exist, present them.
  If a simpler approach exists, say so and push back. If something is unclear, stop and
  ask.
- **Simplicity first.** The minimum code that solves the problem; nothing speculative: no
  extra features, flexibility or error handling nobody asked for. The layers above exist
  to keep the core pure, not to be added for their own sake. If 200 lines could be 50,
  rewrite.
- **Surgical changes.** Every changed line traces to the request. Match existing style.
  Do not refactor or reformat adjacent code; mention unrelated dead code instead of
  deleting it. Remove only the orphans your own change created.
- **Goal-driven.** Turn the task into a check you can run (see Workflow) and loop until
  it passes.

<!-- For maintainers: when an agent repeats a mistake, add one line here. When a rule
never prevents one, delete it. Prefer a test or linter over a sentence. -->
