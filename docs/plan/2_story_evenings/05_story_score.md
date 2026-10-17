---
id: S2-05
title: Story score
status: todo
needs: []
touches: [evening/metrics.py, evening/story_score.py (new), scripts/evening.py, server/runtime.py]
---

# S2-05 — Story score

## Why

"More stories and more chaos" must be a number, or we cannot tell whether a change helped. The event log
already records what happened; we count the moments a player would retell.

## Scope

- In: a pure `evening/story_score.py` that reads the event log and returns counts per kind of moment,
  plus a weighted total.
- In: `metrics.json` of every headless evening gets `story`; the live runtime keeps a running count for
  the closing screen (S2-10).
- In: a baseline for the Locals on seeds 0–9 offline and seed 5 live, written into Results.
- Out: new events. If a moment is not logged today, log it in the task that adds the behavior.

## Shape

Moments counted (event kinds named when frozen), each with a weight in one table:

| Moment | Example |
|--------|---------|
| got drunk | crossed the drunk threshold |
| quarrel | insult, shout, an angry exchange |
| fight | a fight started; knockout counts extra |
| played together | dice, darts, cards with another guest |
| signature act | a guest used their signature item (S2-08) |
| gift or round | gave someone a drink or a thing |
| fell asleep | dozed off at a table |
| left in anger | walked out wronged |

`story: { "moments": {kind: count}, "score": float }`. Weights are a parameter, not module state.

## Steps

1. Test first, parametrized: empty log, one of each moment, duplicates, an unknown kind ignored by rule
   (say why in the test id).
2. Wire into `metrics.json` and the runtime snapshot (`types.ts` with it).
3. Baseline runs and Results.

## Done when

- `make check` passes; `metrics.json` has `story`; the baseline is recorded below.

## Results
