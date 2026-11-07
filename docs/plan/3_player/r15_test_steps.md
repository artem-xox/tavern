---
id: S3-R15
title: One advance and one command for every hall test
status: done
needs: [S3-R00]
touches: [tests]
---

# S3-R15 — Shared test steps

## Why

Every hall test steps the clock and commands actions the same way. `tests/social_hall.py` already exports
`advance(world, seconds)` and `command(verb, target=None)`, and about 50 test files import them from there.
But 14 test files (and `tests/dice_hall.py`) keep **verbatim copies** (an AST comparison, 2026-11-07):

- `advance` (`for _ in range(round(seconds * 10)): step_world(world, 0.1)`): `dice_hall.py`,
  `test_briefing.py`, `test_dice.py`, `test_drunkenness.py`, `test_energy.py`, `test_evening.py`,
  `test_expression.py`, `test_feelings.py`, `test_scenes.py`, `test_turns.py`.
- `command` (`{"id": verb if target is None else f"{verb}:{target}", "verb": verb, "target_id": target}`):
  `test_decisions.py`, `test_drunkenness.py`, `test_expression.py`, `test_feelings.py`,
  `test_intention_runners.py`, `test_lockstep.py`, `test_queues.py`, `test_scene_choices.py`,
  `test_scenes.py`, `test_turns.py`.

The player tasks will add many hall tests; they should find one way to step a hall, not eleven.

## Scope

- In: deleting exactly those copies; each file imports `advance` / `command` from `social_hall` instead,
  the way the other 50 do.
- Out: near-copies that differ in any way, which are part of their file's spec: `advance` with
  `int(seconds * 10)` in `test_social.py` and `test_world.py` (it steps differently for some inputs), the 6
  `event(...)` builders (their defaults differ file to file), `chair(...)` (names differ, and names reach
  briefings). `staff_hall.advance`. Any test body.

## Approval

Test edits: delete the listed helper definitions and add the import line; nothing else in those files.
AGENTS.md "Duplicate once; abstract on the third use". **Approved by the owner, 2026-11-07.**

## Steps

1. Re-run the comparison first: for each listed file, the helper's body must still be identical to
   `social_hall`'s (`python3 -c "import ast,sys; ..."` or by eye); drop a file from the list if it changed.
2. One commit: the deletions and imports. If a file ends up with an unused import (`step_world`), remove it.
   — check: `make test` with the same number of passing cases as before (paste both counts).

## Done when

- `make check` passes, case count unchanged. Pasted into Results.
- `grep -lnE "^def (advance|command)\(" tests/*.py` lists only `social_hall.py`, `staff_hall.py`,
  `test_social.py` and `test_world.py`.

## Results

- Step 1: the comparison was re-run with an AST check (docstrings ignored); all 20 copies still matched `social_hall`.
- Step 2: 20 copies deleted (10 `advance` incl. `dice_hall.py`, 10 `command`), imports added; `step_world` dropped from 9 files where it became unused.
- Cases before: `4706 passed` (`make test`, run started before the edits; `--collect-only` on the stashed baseline also 4706).
- Cases after: `4706 passed in 515.96s` (`make check`; frontend `pass 318`, fail 0).
- The `grep -lnE "^def (advance|command)\(" tests/*.py` also lists `test_closing.py` (`advance` in 0.5 s ticks), `test_evening.py` (`command` with a different id: `verb:target` always) and `test_scenario.py` (`advance` with a `step` argument). They are not on the ticket's list and differ, so they are out of scope; the Done-when line missed them.
