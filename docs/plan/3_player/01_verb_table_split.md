---
id: S3-01
title: Split the verb table
status: todo
needs: []
touches: [backend/tavern/body/activities.py, backend/tavern/body/activity.py (new), backend/tavern/body/effects.py (new), backend/tavern/hall/lifecycle.py, AGENTS.md, docs/plan/TECH_DEBT.md]
---

# S3-01 — Split the verb table

## Why

`body/activities.py` has 687 lines: the `Activity` record (about 115 lines with its docs), twenty effect
functions (about 170 lines), the `ACTIVITIES` table, `FAMILIES` and `client_activities`. D31 left it whole on
purpose and asked for the split when the first player verb arrives. That verb is `walk_to` in
[S3-03](03_hands.md). This task is a pure refactor and does not change the behavior of any evening.

## Scope

- In: three modules where there was one; imports updated; AGENTS.md and TECH_DEBT.md updated to match.
- Out: `walk_to` and any other new verb (S3-03); renaming verbs or fields; changing a table entry.

## Shape

- `body/activity.py`: "What a verb is: the `Activity` record and the signature of its effect." It gets the
  effect alias (the comment at about line 27) and `class Activity`, moved verbatim with their comments.
- `body/effects.py`: "What an activity does when it lands: pour, drink, open a scene, give, shove, go home and
  the rest." It gets `_pour` through `_settle` and `_SHOVES`, moved verbatim. The functions the table imports
  lose their leading underscore, because they are now imported from another module (AGENTS.md, Navigability).
  Helpers used only inside `effects.py` keep it.
- `body/activities.py` keeps `FUN_RELIEF` (if `Activity` reads it, it moves with `Activity`), `ACTIVITIES`,
  `FAMILIES` and `client_activities`. It imports `Activity` and the effects.
- `hall/lifecycle.py` imports `Activity` from `body/activity.py`. Grep for every other importer of a moved name
  and point it to the new module.
- Each of the three files ends up under 400 lines (`wc -l`).
- No change to saves, the snapshot, `types.ts` or prompts.

## Tests that change

None. `tests/test_fun.py` imports `ACTIVITIES, Activity` from `tavern.body.activities`. That keeps working,
because the table module imports `Activity` for its own use. If any test fails, the move has a bug: stop and
report it.

## Steps

1. Baseline: `make golden GOLDEN=runs/golden-base` before the first edit.
2. Move the alias and `Activity` to `body/activity.py` and fix the imports, in its own commit. Check: `make test`,
   then `make golden GOLDEN=runs/golden-now && diff -r runs/golden-base runs/golden-now` prints nothing.
3. Move the effects to `body/effects.py`, rename the imported ones, and fix the imports, in its own commit.
   Check: the same as step 2.
4. Docs: the `body/` line in AGENTS.md lists `activity` and `effects`. The verb recipe ("Adding a verb means one
   `Activity` in `activities.py` …") says that an effect goes in `effects.py`. In TECH_DEBT.md, D31 drops
   `activities.py` from its problem and keeps `scenes.py` and `turn_prompt.py`. Check: `make check`.

## Done when

- `make check` passes, output pasted in Results.
- The golden diff is empty after steps 2 and 3.
- `wc -l backend/tavern/body/activit*.py backend/tavern/body/effects.py`: each file is under 400 lines.

## Results
