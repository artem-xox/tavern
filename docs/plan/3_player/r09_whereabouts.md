---
id: S3-R09
title: Move "where is someone" out of conversation scenes into hall/whereabouts.py
status: done
needs: [S3-R02]
touches: [social/scenes.py, hall/whereabouts.py (new), body/actions.py, body/activities.py, body/bartending.py, body/fights.py, body/projects.py, hall/routes.py, hall/sight.py, hall/world.py, mind/agents.py, social/errands.py, social/hostility.py, social/walk_ups.py, tests]
---

# S3-R09 — Whereabouts

## Why

The player will need "who can I reach from here" (to talk, hand over, hit) on every click. That rule exists,
but it lives in `social/scenes.py` (527 lines, over the 400 limit), mixed with the life of a conversation.
Five spatial helpers there are imported by `body/` and `hall/` modules that have nothing to do with scenes,
which is most of why `hall/` imports `social/`:

| Function | Imported by |
|----------|-------------|
| `table_of` | `body/actions.py`, `body/projects.py` |
| `at_table` | `body/actions.py`, `hall/routes.py`, `hall/sight.py`, `mind/agents.py`, `social/errands.py`, `social/walk_ups.py` |
| `bar_of` | `body/bartending.py` |
| `side_by_side` | `body/actions.py`, `body/activities.py`, `hall/routes.py`, `hall/world.py`, `social/hostility.py` |
| `within_reach` | `body/actions.py`, `body/fights.py`, `body/projects.py`, `hall/routes.py`, `hall/sight.py` |

They need only `hall/` modules (`room.find_object`, `sightlines.line_visible`, `staff.on_staff`) and the
private `_lines` (who stands where in a queue).

## Scope

- In: a new `backend/tavern/hall/whereabouts.py` ("Where a visitor is: at which table or bar, and whom they
  can reach") holding `table_of`, `at_table`, `bar_of`, `side_by_side`, `within_reach` and `_lines`, moved
  verbatim with their docstrings and comments; every import updated; `scenes.py` imports them from there.
- Out: `pressed` and `conversation_of` (conversation concepts; they stay in `scenes.py`). Renames.

## Approval

Test edits, import lines only, **approved by the owner, 2026-11-07**: `tests/test_approach.py`, `tests/test_scenes.py`,
`tests/test_bar_chat.py`, `tests/test_table_reach.py` import the moved names from `tavern.hall.whereabouts`.

## Steps

1. Create `hall/whereabouts.py` with the six functions cut from `scenes.py`; fix imports in `scenes.py`
   and in every module of the table; fix the four test files' import lines. One commit.
   — check: `grep -rnE "from tavern.social.scenes import .*\b(table_of|at_table|bar_of|side_by_side|within_reach)\b" backend tests scripts`
   finds nothing; `make test`; `.venv/bin/mypy`; golden empty diff.
2. Do not add a test file: the moved functions keep their specs where they are. Instead, the module
   docstring's second paragraph says where they are specified: `tests/test_scenes.py`,
   `tests/test_approach.py`, `tests/test_table_reach.py`, `tests/test_bar_chat.py`. Same commit as step 1.
3. `scenes.py` shrinks by the moved code (about 115 lines, to about 410). It stays slightly over the limit;
   do not split it further in this task.

## Done when

- `make check` passes; golden check prints nothing. Pasted into Results.
- `hall/whereabouts.py` imports nothing from `social/`, `mind/` or `evening/`.

## Results

Done 2026-11-07. `hall/whereabouts.py` holds the six functions moved verbatim (imports only `hall/` modules);
`scenes.py` is 408 lines (was 527); every importer and the four test files' import lines updated; three
comments naming `scenes.side_by_side` now name `whereabouts.side_by_side`.

- `make check`: `4649 passed in 343.46s`, frontend `318 pass, 0 fail`, mypy `Success: no issues found in 133 source files`.
- Step-1 grep for the moved names imported from `tavern.social.scenes`: no output.
- `make golden GOLDEN=runs/golden-now && diff -r runs/golden-base runs/golden-now`: no output (empty).
