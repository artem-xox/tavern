---
id: S2-05
title: Story score
status: done
needs: []
touches: [evening/story_score.py (new), evening/recap.py (new), scripts/evening.py, server/runtime.py, frontend/src/]
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

Built:

- `evening/story_score.py`: `story_moments(events)` picks the moments, `story_score(moments, weights)` counts
  them per kind and weighs them. Weights are `WEIGHTS`, passed as an argument.
- Moments counted, from events logged today: `quarrel` (2; the `quarrel` event, an `insulted` beside it is not
  counted again), `fight` (4; `fight_started`), `knockout` (3 extra; `fight_ended` whose words say someone was
  knocked out), `played_together` (1; `dice_won`), `gift` (1; `gave`), `fell_asleep` (2; `dozed_off`),
  `limped_home` (2; battered and gone). A quarrel, fight or gift logs one event per participant: same type, time
  and message count once.
- Not counted, because nothing logs them yet (the task that adds the behavior adds one weight and one rule):
  got drunk, signature act, leaving in anger.
- `story` in `metrics.json`; the live snapshot has `story` and `recap` (`types.ts` with it); a "Story of the
  evening" card in the dashboard.
- Added on request: `evening/recap.py` asks a storyteller model (Claude Sonnet 5.5) for a short, playful retelling
  with emoji: `{ "title", "text" }`, checked in `parse_recap`. Headless evenings with `ANTHROPIC_API_KEY` write
  `recap.md`; the live server retells once, when the last guest leaves. A failed retelling is said in the event
  log and the score stays. S2-10 (cited chapters, closing screen) builds on this and replaces it.

Baseline, Locals, offline (`--mode local --writer scripted`), seeds 0–9: score 3, 5, 2, 2, 4, 3, 4, 3, 2, 7; mean 3.5.
Every evening has a nap; only seed 9 has quarrels (3); nobody fights. Live seed 5 is not recorded: no Jev or
Claude key was available in the session that built this.

Not run: the Sonnet call itself (no key); it is covered by a fake port, and `ask_claude` by its own tests.
