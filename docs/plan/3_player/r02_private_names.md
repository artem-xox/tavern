---
id: S3-R02
title: Make the module-local functions private
status: todo
needs: [S3-R00]
touches: [adapters/database.py, body/bartending.py, body/fights.py, body/projects.py, body/wounds.py, evening/scenario.py, mind/intentions.py, mind/signature_candidates.py, social/aims.py, social/bystanders.py, social/dice.py, social/invitations.py, social/scenes.py, social/signature_acts.py, social/turns.py]
---

# S3-R02 — Module-local functions get an underscore

## Why

AGENTS.md: "Anything not imported elsewhere is `_private`." An import scan (2026-11-07) found 19 public
functions that no other module, script or test imports. A reader cannot tell them from a module's real API,
which is what the player tasks will be built against.

## Scope

- In: renaming exactly the functions below to `_<name>`, every use inside their module, and the comments in
  other modules that name them.
- Out: types (`TypedDict`, dataclasses, aliases such as `Ticket`, `Observation`): they appear in public
  signatures and stay public. Constants. `card_compiler.card_question` (R03 deletes the module).

## The functions

| Module (`backend/tavern/`) | Function | Comments elsewhere that name it |
|----------------------------|----------|---------------------------------|
| `adapters/database.py` | `load_database_world`, `save_database_world` | — |
| `body/bartending.py` | `order_at` | — |
| `body/fights.py` | `weapon_of`, `sex_of` | `body/items.py` about line 49 (`tavern.body.fights.weapon_of`) |
| `body/projects.py` | `project_error` | — |
| `body/wounds.py` | `mend` | — |
| `evening/scenario.py` | `parse_guest`, `parse_staff_member` | `hall/arrival.py` about line 26 (`scenario.parse_guest`) |
| `mind/intentions.py` | `latest_trigger` | — |
| `mind/signature_candidates.py` | `offered_verbs` | — |
| `social/aims.py` | `aim_of` | — |
| `social/bystanders.py` | `fighters_in_sight` | — |
| `social/dice.py` | `form` | — |
| `social/invitations.py` | `counter_kinds` | — |
| `social/scenes.py` | `has_run_its_course` | — |
| `social/signature_acts.py` | `log_act`, `in_sight` | `mind/signature_candidates.py` about line 23 (`signature_acts.in_sight`) |
| `social/turns.py` | `cutting_in` | — |

Careful with `form` and `mend`: they are also English words in prose all over the tree. Rename the
identifier only (`def form(`, `form(` calls, `` `form` `` in this module's own docstrings), never prose.
The string `"cutting_in"` in `body/activities.py` and the scene key `scene.get("cutting_in")` in
`mind/haiku_turns.py` are a family name and a view field, not this function: leave them.

Archive files under `docs/plan/*/archive.md` are history: do not edit them.

## Steps

1. Before starting, re-run the check that the list is still right, for each name:
   `grep -rnw <name> backend scripts tests` must show uses only in its own module (plus the comments above).
   For `form` and `mend` grep the code shape instead, since the words are everywhere in prose:
   `grep -rnE "\b(form|mend)\(|import .*\b(form|mend)\b" backend scripts tests` (on 2026-11-07: only
   `body/wounds.py` and `social/dice.py`). A name that gained an outside use stays public: note it in Results.
2. Rename, one commit per package (`adapters`, `body`, `evening`, `mind`, `social`). — check after each:
   `make test` and `.venv/bin/mypy`.
3. Golden check of R00 — empty diff.

No test edits: no test imports any of these names. If one fails, the rename missed a use.

## Done when

- `make check` passes; the golden check prints nothing. Both pasted into Results.
- `grep -rnwE "def (load_database_world|save_database_world|order_at|weapon_of|sex_of|project_error|mend|parse_guest|parse_staff_member|latest_trigger|offered_verbs|aim_of|fighters_in_sight|form|counter_kinds|has_run_its_course|log_act|in_sight|cutting_in)\(" backend`
  finds nothing.

## Results

Filled in when the task is done.
