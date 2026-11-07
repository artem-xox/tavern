---
id: S3-R13
title: Wire an evening once: one AI config reader, one Claude config, one mind loop builder, one end rule
status: todo
needs: [S3-R04]
touches: [mind/selection.py, adapters/claude.py, evening/mind_loop.py, hall/closing.py, server/runtime.py, evening/lockstep.py, app.py, scripts/evening.py, docs/plan/TECH_DEBT.md, tests]
---

# S3-R13 — One wiring for both runners (D09)

## Why

TECH_DEBT D09: "Model wiring is written twice, and the copy in the entry point is untested". The live server
(`app.py` → `server/runtime.py`) and the headless runner (`scripts/evening.py` → `evening/lockstep.py`) each
build the same things by hand. The player will be a third consumer of the same loop; it must plug in once.

| Built twice | Live | Headless |
|-------------|------|----------|
| The AI config from the environment | `app.create_default_app` (`config = {...}`, about line 42) | `scripts/evening.config` |
| A Claude request config `{"anthropic_api_key", "model", "timeout": 30.0, "retries": 1}` | `app._claude_port` | `scripts/evening.turn_writer`, `.stage_writer`, `.mind` (60 s in `.write_retelling`) |
| The `MindLoop`, binding config and generator into each port with lambdas | `TavernRuntime.__init__` | `lockstep.run_evening` |
| "Everyone has left and nobody else is expected" | `runtime._anyone_to_come` | `lockstep.evening_over` |

## Scope

- In: four shared functions, each tested, and both runners and both entry points using them.
- Out: how each entry point wraps the Jev evaluators (the live one notes health, the headless one records and
  replays): that difference is real. Any change in what an evening does.

## Shape

```python
# mind/selection.py
def read_ai_config(values: Mapping[str, str | None], key: str | None) -> dict[str, Any]
#   {"typesafe_api_key": key, "model", "timeout", "temperature", "answers"} from TYPESAFE_MODEL, AI_TIMEOUT,
#   AI_TEMPERATURE, AI_ANSWERS with today's defaults; ValueError naming the variable for a malformed number.

# adapters/claude.py
def claude_config(key: str, model: str, timeout: float = 30.0) -> dict[str, Any]   # retries=1, as today

# evening/mind_loop.py
@dataclass(frozen=True)
class EveningPorts:  # choose, answer (None: the line writer decides), write, stage, intender (None offline)
def evening_mind(courier: Courier, ports: EveningPorts, rules: IntentionRules) -> MindLoop

# hall/closing.py
def all_gone(world: Mapping[str, Any]) -> bool   # no guest in the hall and nobody expected
```

The ports in `EveningPorts` already have the config and generator bound: each runner binds its own (the
runtime reads `self.ai_config` and `self.rng`; lockstep its `config`, `rng` and `evaluators`).

## Steps

1. Red/green, `tests/test_lean_requests.py` (where `read_switch` is specified) or a new
   `tests/test_ai_config.py`: `read_ai_config` cases — empty environment (defaults), every variable set,
   `AI_TIMEOUT=soon` (ValueError naming `AI_TIMEOUT`), `AI_ANSWERS=maybe` (ValueError). One commit.
2. Refactor: `app.py` and `scripts/evening.config` call it (the script keeps choosing the key by mode). Commit.
3. Red/green, `tests/test_claude.py`: `claude_config` returns today's dict. Refactor its five copies. Commit.
4. Red/green, `tests/test_closing.py`: `all_gone` — guests present, only staff present, nobody but someone
   expected, nobody at all. Refactor `runtime._anyone_to_come` away and `lockstep.evening_over` onto it. Commit.
5. Refactor: `evening_mind` and `EveningPorts`; `TavernRuntime.__init__` and `run_evening` build their loop
   with it. `tests/test_mind_loop.py` keeps constructing `MindLoop` directly; it stays green unchanged. Commit.
6. TECH_DEBT.md: delete row D09. Same commit as step 5.

Golden check after every commit: empty diff. `tests/test_lockstep.py`, `tests/test_runtime_story.py`,
`tests/test_app.py`, `tests/test_sessions.py` green unchanged.

## Done when

- `make check` passes; golden check prints nothing. Pasted into Results.
- `grep -n '"retries": 1' backend scripts` finds only `claude_config`; `grep -n "lambda" backend/tavern/server/runtime.py backend/tavern/evening/lockstep.py`
  shows only the port bindings.

## Results

Filled in when the task is done.
