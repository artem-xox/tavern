---
id: S3-R05
title: One event log, one length, one way to read what is new
status: todo
needs: [S3-R02]
touches: [hall/memory.py, evening/decisions.py, server/runtime.py, evening/lockstep.py, social/speeches.py, social/bystanders.py, social/turns.py, social/heckles.py, social/signature_acts.py, hall/closing.py, tests/test_decisions.py]
---

# S3-R05 — One event log

## Why

The event log is the story's source of truth, and the player's acts will be logged into it like a guest's.
Today it has three problems:

1. **A bug.** `memory.record_event` and `memory.log_event` keep the latest 200 events, but
   `decisions.log_control` keeps 100 (`world["events"] = world["events"][-100:]`). Every refused or failed
   decision and every operator command halves the log that rules read (`stage_lines` heckles,
   `projects._no_game`, intention triggers).
2. **Seven modules patch the event just logged** through `world["events"][-1]`: `social/speeches.py:109`,
   `social/bystanders.py:49`, `social/turns.py:384`, `social/heckles.py:49` and `:64`,
   `social/signature_acts.py:46`, `hall/closing.py:69`. They rely on nothing else having logged in between.
3. **Two runners find the new events two ways.** `TavernRuntime._note_story` and `lockstep._collect` both scan
   back for the last event seen, by identity; when it was trimmed away, one silently takes the whole log again
   (duplicating story moments), the other raises.

## Scope

- In: the three fixes above.
- Out: what events contain (R06, R07); the 200-event length itself.

## Shape

```python
def record_event(world, actor, kind, message, outcome=None) -> dict[str, Any]   # returns the logged event
def log_event(world, actor_id, kind, message) -> dict[str, Any]                # returns the logged event
def fresh_events(events: Sequence[Mapping[str, Any]], last: Mapping[str, Any] | None) -> list[dict[str, Any]] | None
```

`fresh_events` lives in `hall/memory.py`: the events after `last` (found by identity, scanning from the end),
all of them when `last` is None, and None when `last` is no longer in the log. Each runner keeps its own
policy for None: lockstep raises its current `ValueError`, the runtime takes the whole log as today.
`decisions.log_control` is deleted; its callers call `log_event(world, None, "control", message)`.

## Steps

1. **Red**, `tests/test_decisions.py`: a world with 150 events, `apply_decision` with an outcome that raises
   → 151 events, the last a `control` event. Fails today (100). — check:
   `.venv/bin/python -m pytest tests/test_decisions.py -k control -x`.
2. **Green**, one commit (behavior change: the bug fix): replace `log_control` with `log_event` in
   `evening/decisions.py` and `server/runtime.py`; delete `log_control`. The golden log **may differ** from
   here on (rules now see older events); paste the `diff --stat` into Results. Record this commit's output,
   `make golden GOLDEN=runs/golden-r05`, and check every later step of this task against it, not against
   `runs/golden-base`.
3. **Red/green**, `tests/test_shared_helpers.py`: `record_event` and `log_event` return the event they
   appended (`is world["events"][-1]`). One commit.
4. **Refactor**, one commit: the seven sites use the returned event (`record_event(...).update(line=...)`).
   `signature_acts.log_act` keeps updating the memory entry too, and `speeches` keeps its
   `speaker["memory"][-1]` line: memories are not part of this step. — check: golden vs `runs/golden-r05`,
   empty diff.
5. **Red/green**, `tests/test_shared_helpers.py`: `fresh_events` cases — no last (all), last in the middle,
   last at the end (empty), last trimmed away (None), equal-but-not-identical event (not found). One commit.
6. **Refactor**, one commit: `TavernRuntime._note_story` and `lockstep._collect` call `fresh_events`. — check:
   `tests/test_lockstep.py` and `tests/test_runtime_story.py` unchanged and green; golden empty diff.

## Done when

- `make check` passes; golden diffs as described. Both pasted into Results.
- `grep -rn 'world\["events"\]\[-1\]\|log_control' backend` finds nothing.

## Results

Filled in when the task is done.
