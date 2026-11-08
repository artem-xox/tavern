---
id: S3-R13
title: Wire an evening once: one AI config reader, one Claude config, one mind loop builder, one end rule
status: done
needs: [S3-R04]
touches: [mind/selection.py, scripts/dialogue_eval.py, adapters/claude.py, evening/mind_loop.py, hall/closing.py, server/runtime.py, evening/lockstep.py, app.py, scripts/evening.py, docs/plan/TECH_DEBT.md, tests]
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

Commits on `claude/s3-r13-wiring-bd29dd`, one per step (steps 5 and 6 share one):
`82e9f17` read_ai_config, `0710d8d` app and script use it, `7bdb3f1` claude_config, `6afbed8` all_gone,
`b815756` evening_mind and EveningPorts, D09 deleted.

Notes:
- R04 had already removed the lean/aims/projects switches, so `read_ai_config` reads only the key, model,
  timeout, temperature and answers, as the Shape says.
- `scripts/dialogue_eval.py` also held a `"retries": 1` copy; it uses `claude_config` too, so the done-when
  grep holds. `probes.py` keeps `retries: 0` on purpose (a different config).
- `lockstep.evening_over` stays (its tests call it) and now delegates to `all_gone`.
- Red phases for new functions failed at import (the function did not exist yet), not on an assertion.
- New tests: `tests/test_ai_config.py`, `tests/test_evening_mind.py`, and cases in `test_closing.py`,
  `test_claude.py`. No existing test was edited.

Golden check after every commit: `diff -r runs/golden-base runs/golden-now` printed nothing (also after the last).

`make check`: `4660 passed in 358.47s (0:05:58)`; frontend `ℹ tests 318 / ℹ pass 318 / ℹ fail 0`; exit 0.

`grep -n '"retries": 1' backend scripts` finds only `adapters/claude.py:145` (`claude_config`). The remaining
`lambda`s in `runtime.py` and `lockstep.py` are the port bindings plus the unrelated command handlers.
