---
id: S3-R11
title: Split agents.py: the options a guest has, apart from how one is chosen
status: doing
needs: [S3-R01, S3-R04, S3-R08]
touches: [mind/agents.py, mind/candidates.py (new), evening/metrics.py, AGENTS.md, tests]
---

# S3-R11 — Candidates apart from choosing

## Why

`mind/agents.py` (547 lines) does two jobs. Lines 31–390 list what a guest could do now, from their
observation: `build_candidates` (first-stage options, one per family), `build_seat_candidates`, and about
twenty private builders (`_concrete_candidates`, `_social_candidates`, `_gifts`, `_seat_wish`, ...). Lines
391–547 choose among them: `choose_action`, `choose_answer`, `Evaluators`, `_decide`, the evaluator views.

The player tasks need the first job without the second: an action menu, or a check that a clicked action is
on offer. Its docstring needs an "and" (AGENTS.md, rule S): split it.

## Scope

- In: a new `backend/tavern/mind/candidates.py` ("The options open to a guest now, from what they observe"),
  moved verbatim: `KEEPS_OWN_MUG`, `SLEEPY`, `SETTLES_IN`, the `Action` `TypedDict`, `build_candidates`,
  `build_seat_candidates` and every private helper only they use. `agents.py` keeps `EvaluatorError`,
  `Evaluator`, `Evaluators`, `choose_action`, `choose_answer` and the private helpers of choosing
  (`_unwired`, `_at_chair`, `_aimed`, `_stage`, `_evaluator_view`, `_in_line`, `_aim_view`, `_decide`).
- One helper is shared: `_action` (28 uses among the builders, one in `agents._at_chair`). It moves to
  `candidates.py` as public `action(verb, target=None, item=None) -> Action`, with a docstring; both modules
  call it.
- Out: any change to which candidates are offered or how they are scored.

## Approval

Test edits, import lines only, **approved by the owner, 2026-11-07**: 34 test files import `build_candidates` (2 also
`build_seat_candidates`) from `tavern.mind.agents`; they import them from `tavern.mind.candidates`
(`grep -lwE "build_candidates|build_seat_candidates" tests/*.py`). Imports of `Evaluators`, `choose_action`,
`choose_answer`, `Evaluator` stay as they are.

## Steps

1. Create `candidates.py` with the moved code; `agents.py` imports `Action`, `action`, `build_candidates`,
   `build_seat_candidates` from it; update every other importer (`grep -rn "from tavern.mind.agents import" backend scripts`
   — move each name to the module that now owns it) and the docstring reference in `evening/metrics.py`
   (about line 359, `tavern.mind.agents.SLEEPY` → `tavern.mind.candidates.SLEEPY`). The approved test import
   edits. One commit.
   — check: `make test`, `.venv/bin/mypy`, golden empty diff; `wc -l` of both files (about 380 and 170).
2. AGENTS.md, "Extending" → "Adding a verb": "its candidate rule in `agents.py`" becomes "in `candidates.py`".
   Same commit.

## Done when

- `make check` passes; golden check prints nothing. Pasted into Results.
- `candidates.py` imports nothing from `agents.py`; `grep -c "def _" backend/tavern/mind/agents.py` counts
  only choosing helpers.

## Results

Filled in when the task is done.
