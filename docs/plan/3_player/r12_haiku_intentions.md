---
id: S3-R12
title: Split intentions.py: how Haiku is asked for an intention, apart from when and what it changes
status: done
needs: [S3-R00]
touches: [mind/intentions.py, mind/haiku_intentions.py (new), app.py, scripts/evening.py, adapters/tracing.py, tests]
---

# S3-R12 — Haiku's intention question in its own module

## Why

`mind/intentions.py` (536 lines) holds four things: when a guest takes stock (triggers, `intention_due`,
`intention_requests`, `stale_intentions`), what the mind is shown (`intention_view`), **how Haiku is asked
and answered** (`intention_question`, `_schema`, `parse_stance`, `intention_writer` and the text helpers
`_wishes`, `_previous`, `_duty`, `_others`, `_earlier`), and how an answer changes the world
(`check_intention`, `deliver_intention`, `check_saved_intention`).

Lines and stage numbers already keep their model side apart: `mind/haiku_turns.py`, `mind/haiku_stage.py`.
The player's typed lines will need a similar model module; the three should look alike.

## Scope

- In: a new `backend/tavern/mind/haiku_intentions.py` ("How Claude Haiku is asked for a guest's intention,
  and how its answer is read"), holding verbatim `intention_question`, `_schema`, `parse_stance`,
  `intention_writer` and every private helper and constant **only they** use. A helper or constant that
  `intention_view`, `check_intention` or `deliver_intention` also uses stays in `intentions.py` (if it is
  private and now needed by both, make it public in `intentions.py` with a docstring).
- Out: `Intender` (the port stays beside its consumer, `intentions.intention_requests` / `mind_loop`);
  any change to the question's text, schema or parsing.

## Approval

Test edits, import lines only, **approved by the owner, 2026-11-07**: the tests that import `intention_question`,
`intention_writer` or `parse_stance` from `tavern.mind.intentions`
(`grep -lwE "intention_question|intention_writer|parse_stance" tests/*.py`; 3 files on 2026-11-07).

## Steps

1. Create `haiku_intentions.py`; update `app.py`, `scripts/evening.py`, `adapters/tracing.py` and any other
   importer (`grep -rnwE "intention_question|intention_writer|parse_stance" backend scripts`); the approved
   test import edits. One commit. — check: `make test`, `.venv/bin/mypy`, golden empty diff.
2. A replay of a recorded live evening, if one exists on the machine (`ls runs/*/calls.jsonl`), proves the
   question is byte-identical: `make evening MODE=replay CALLS=<that>/calls.jsonl OUT=runs/r12-replay SEED=<its seed>`
   and `cmp <that>/events.jsonl runs/r12-replay/events.jsonl`. If none exists, say so in Results; the
   golden check does not ask Haiku.

## Done when

- `make check` passes; golden check prints nothing. Pasted into Results.
- `intentions.py` (about 390 lines) builds no question text; do not move anything else to get under a number.

## Results

Done 2026-11-07.

- Step 1: `mind/haiku_intentions.py` (143 lines) holds `intention_question`, `_schema`, `parse_stance`,
  `intention_writer`, `_wishes`, `_previous`, `_duty`, `_others`, `_earlier`, moved verbatim. `intentions.py` is 401 lines.
  `check_intention` (with `_is_goal`, `_LONGEST`, `_ANSWER_FIELDS`) stays: it applies an answer. Importers updated:
  `app.py`, `scripts/evening.py`; `adapters/tracing.py` needed no edit (it imports only `Intender`, `Written`).
  Approved test import edits in 5 files, not 3: `test_heard`, `test_duty_stance`, `test_address_room`, `test_goals`,
  `test_intentions`.
- Golden: `make golden GOLDEN=runs/golden-now && diff -r runs/golden-base runs/golden-now` printed nothing.
- `make test`: 4706 passed; `.venv/bin/mypy`: no issues found in 134 source files; `make check`: passed
  (backend tests, mypy, frontend typecheck, 318 frontend tests, 0 failed).
- Step 2: no recorded live evening exists on this machine (`ls runs/*/calls.jsonl` matches nothing, in this
  worktree or the main checkout), so the byte-identical replay was not run. The golden check does not ask Haiku.

