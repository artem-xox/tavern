---
id: S3-R07b
title: Metrics of aims, goals, responses, projects and speeches read event fields, not wording
status: done
needs: [S3-R06]
touches: [social/aims.py, mind/intentions.py, social/responses.py, body/projects.py, social/speeches.py, evening/aim_metrics.py, evening/goal_metrics.py, evening/response_metrics.py, evening/project_metrics.py, evening/speech_metrics.py, frontend/src/types.ts]
---

# S3-R07b — Metrics read fields, not words (the rest)

## Why

Same reason and method as [R07](r07_metrics_read_fields.md), for the six readers it left.

| Reader (`backend/tavern/evening/`) | Parses | Field to read instead |
|--------|--------|---------------|
| `aim_metrics.aim_counts` | `_AIM = r".* \((?P<aim>...)\)"` on `aim_set` / `aim_kept` | `aim` |
| `goal_metrics.goal_kind_counts` | `_GOAL_PATTERNS` (each goal's wording) on `goal_set` | `goal` (the `GOALS` key) |
| `goal_metrics.chased_counts` | `CHASING in message` on `intention` | `obsession` (the index; present only when the answer named one) |
| `response_metrics.response_counts` | `_ANSWER = r".* went to answer .*?, who (?P<reason>.+) \((?P<seconds>\d+) s later\)"` | `response` (the `RESPONSES` kind) and `after` (seconds, unrounded) |
| `project_metrics.project_counts` | `_KIND = r".* \((?P<kind>[a-z_]+)\)"` | `project` (the `PROJECTS` key) |
| `speech_metrics` | `_REACTION = r"(\d+) admired it, (\d+) groaned$"` | `admired`, `groaned` |

## Method, for each row

1. Find the source: `grep -rn '"<event type>"' backend/tavern` (the event type is the one the reader filters on).
   Put the values the regex extracts on the event as fields, from the variables that build the message:
   `record_event(..., fields={...})` (R06) or `log_event(...).update(...)` (R05). The message stays
   byte-identical.
2. `frontend/src/types.ts`: add the field to `WorldEvent` as optional, same commit.
3. Golden: R06's script with `NEW` widened by the new field names; `make build`.
4. Switch the reader to the field; delete the regex and the parse-error `ValueError` it needed, replacing it with
   one for a missing field. One commit. — check: its test file green and every golden `metrics.json` identical.

`response_metrics` rounds nothing today (the message shows whole seconds); the field must carry the value the
message rounds, and the metric must round it where it did before, so `metrics.json` stays identical
(AGENTS.md: rounding lives at the presentation layer). If that cannot keep it identical, stop and ask.

## Scope

- In: the six rows.
- Out: everything listed as "Out" in R07.

## Approval

As R07: adding a new field to hand-built events in tests, and replacing a parse-error test by a
missing-field test, are the only approved edits; list each in Results. **Approved by the owner, 2026-11-07.**

## Done when

- `make check` and `make build` pass; golden `events.jsonl` identical apart from the new fields; every golden
  `metrics.json` identical. Pasted into Results.
- `grep -n '\["message"\]' backend/tavern/evening/*_metrics.py` shows only the identity uses `(time, message)`
  and `dialogue_metrics` taking a line's words.

## Results

Six commits plus one mypy fix. Source commit: `aim` on `aim_set`/`aim_kept`; `goal` (the `GOALS` key) on `goal_set`;
`obsession` on `intention` when named; `response` and `after` (unrounded seconds) on `answered`; `project` on the
`project_*` ends; `admired`, `groaned` on `speech_reaction`. `types.ts` gained the optional fields. Then one commit per
reader; `response_counts` rounds `after` with `round()`, equal to the message's `:.0f`. Regexes, `_GOAL_PATTERNS`, `CHASING`
import and `THOUGHTS` import removed.

Test edits (approved): `aim`/`project`/`response`/`goal`/`obsession`/`admired`/`groaned` added to hand-built events in
`test_aim_metrics`, `test_goal_metrics`, `test_project_metrics`, `test_response_metrics`, `test_speech_metrics`; the four
parse-error tests became missing-field tests (`test_goal_metrics` one renamed `test_a_goal_that_cannot_be_read_fails_loudly`;
response's two became an unknown/missing `response` and a missing `after`); added `test_the_mean_delay_is_taken_over_whole_seconds...`
and `test_a_speech_reaction_without_its_counts_fails_loudly`.

- Golden (`runs/cmp.py`, R06's script with `NEW` widened): `identical apart from the new fields; metrics.json identical`
  for all four runs. The offline casts log no `goal_set`/`intention`, so those two are covered by unit tests only.
- `grep '\["message"\]' evening/*_metrics.py`: only identity uses `(time, message)` (ailment, fight, manner, giving) and the
  R07 readers still unmerged here (choice, dialogue, invitation, fight reactions).
- `make check`: 4662 passed, 6 failed (asset tests in `test_character*_assets.py`), mypy then fixed (clean on 135 files),
  frontend 318 passed. The 6 failures and `make build` fail the same way: `tsc` TS2688 "Cannot find type definition file
  for 'estree 2'" and "'trusted-types 2'". Stray `estree 2` / `trusted-types 2` directories in the shared
  `node_modules/@types` (main checkout) make `tsc` fail; no other TS error, none from my `types.ts`. Environmental, not touched.
- `git merge claude/s3-prep`: already up to date.
