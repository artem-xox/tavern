---
id: S3-R01
title: Delete dead code, a dead script and a duplicated plan file
status: todo
needs: [S3-R00]
touches: [body/wounds.py, mind/agents.py, mind/model_health.py, adapters/claude.py, evening/recording.py, hall/world.py, scripts/benchmark_cost.py, Makefile, tests/test_turn_metrics.py, tests/test_recording_claude.py, docs/plan/2_story_evenings]
---

# S3-R01 — Delete what nothing uses

## Why

An AST scan of every module (2026-11-07) found top-level names that no module, script or test reads, one
production constant only a test reads, a script that monkeypatches a private adapter function, and a stale
copy of a plan file. Each is noise for whoever writes the player tasks.

## Scope

- In: exactly the items below.
- Out: the card compiler (R03), the AI switches (R04), renaming module-local names (R02).

## The items

| # | What | Evidence |
|---|------|----------|
| 1 | `BATTERED` in `backend/tavern/body/wounds.py:20` | referenced nowhere (`grep -rnw BATTERED backend scripts tests` finds only the definition; the frontend has its own) |
| 2 | `class Decision` in `backend/tavern/mind/agents.py:84` | referenced nowhere; the live one is `hall.state.Decision` |
| 3 | `STATUSES` in `backend/tavern/mind/model_health.py:10` | referenced nowhere |
| 4 | `HAIKU_4_5` in `backend/tavern/adapters/claude.py:15` | only two tests read it (`tests/test_turn_metrics.py`, `tests/test_recording_claude.py`); every real evening uses `HAIKU_5_5`. Also fix the docstring of `evening/recording.py` (about line 304) that names it as the example: name `claude.HAIKU_5_5` |
| 5 | `scripts/benchmark_cost.py`, the `benchmark` target, its `.PHONY` entry and its help line in `Makefile` | from the Stage 0 demo; it swaps the private `jev._post_scores` at runtime. `make evening` already meters every call and prices it in `metrics.json` |
| 6 | `docs/plan/2_story_evenings/13_livelier_talk 2.md` (with the space) | an older copy of `13_livelier_talk.md` without its Results |
| 7 | the two `from tavern.social.responses import ...` lines in `backend/tavern/hall/world.py` | merge into one line: `from tavern.social.responses import mark_answered, note_calls` |

## Approval

Item 4 edits two test files: `tests/test_turn_metrics.py` and `tests/test_recording_claude.py` stop
importing `HAIKU_4_5` and each defines the same tariff locally,
`HAIKU_4_5 = Tariff(input=1.0, output=5.0, cache_read=0.10, cache_write=1.25)` (both already import
`Tariff`). Reason: a retired model's price is test data, not a production constant. No assertion changes.
**Approved by the owner, 2026-11-07.**

## Steps

1. Items 1–3 and 7, one commit. — check: `make test`, `.venv/bin/mypy`, golden check of R00 (empty diff).
2. Item 4, one commit (the approved test edit). — check:
   `.venv/bin/python -m pytest tests/test_turn_metrics.py tests/test_recording_claude.py`.
3. Item 5, one commit. — check: `make help` no longer lists `benchmark`;
   `grep -rn "benchmark" Makefile README.md docs/*.md AGENTS.md` finds nothing that points at the script.
4. Item 6, one commit with `git rm "docs/plan/2_story_evenings/13_livelier_talk 2.md"`.

Before deleting anything, grep for the name once more (`grep -rnw <name> backend scripts tests frontend/src`):
if a use appeared since 2026-11-07, stop and report it instead of deleting.

## Done when

- `make check` passes; the golden check prints nothing. Both outputs pasted into Results.
- The seven items are gone and nothing else changed.

## Results

Filled in when the task is done.
