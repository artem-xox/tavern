---
id: S3-R14
title: Build the evening report in the core, not in the entry point
status: todo
needs: [S3-R04]
touches: [scripts/evening.py, evening/report.py (new), tests/test_report.py (new)]
---

# S3-R14 — The evening report

## Why

`metrics.json` is the measure of every change, and the player's Stage 3 will add its own counts to it. Today
the report is assembled inside `scripts/evening.main` (about lines 392–424): 38 top-level keys, a dozen
imports of metric functions, the names-by-ID maps built inline twice, and no test. AGENTS.md: "Entry points
only do I/O and wiring; logic is importable and testable without files or network."

## Scope

- In: a new `backend/tavern/evening/report.py` ("The measurements of one headless evening, gathered into
  the report `make evening` writes") with one public function; the script calls it.
- Out: the `run` section (it describes how the script was invoked: the script keeps building it and passes it
  in); `rounded()` (presentation: stays in the script); any change to a metric.

## Shape

```python
def evening_report(evening: Evening, world: World, calls: Sequence[Record], run: Mapping[str, Any],
                   input_usd_per_million: float, stuck_threshold: float,
                   tariffs: Mapping[str, Tariff], writer_tariff: Tariff) -> dict[str, Any]
```

Returns exactly what `report` holds today, same keys in the same order (the order is visible in
`metrics.json`): `run`, then the keys of `evening_metrics`, then `intentions` … `writer` as the script lists
them. `names` (actor ID → name over present and departed) is built once, privately.

## Steps

1. Red, `tests/test_report.py`: play a short offline evening with the shared helpers (for example
   `tests/staff_hall.py` or a lockstep run over the repository hall with `Pace(0.1, 1.0, 60.0)`), call
   `evening_report` and assert (a) its keys, in order, equal the 38 listed below, (b) `report["story"]`
   equals `story_score(story_moments(evening.events), WEIGHTS)`, (c) `report["run"]` is the mapping passed
   in. Fails: no module.
2. Green: move the dict literal from the script into `evening_report` verbatim; the script calls it. One
   commit. — check: every golden `metrics.json` **byte-identical** (`diff -r` on the golden directories).
3. The script loses the imports only the report used; `scripts/evening.py` shrinks by about 50 lines.

Keys on 2026-11-07, in order: `run, game_seconds, guests, departures, completed, conversations, quarrels,
decisions, errors, cost, stuck, intentions, repetition, choice, responses, aims, projects, invitations, goals,
goal_kinds, chased, promises, attention, conversation, news, dice, sleep, drink, speeches, stage, giving,
manners, closing, ailment, fights, story, bar, writer`.

## Done when

- `make check` passes; golden check prints nothing. Pasted into Results.
- `scripts/evening.py` imports no `*_metrics` module.

## Results

Filled in when the task is done.
