---
id: S3-R04
title: Retire the lean, aims and projects switches, so tests run the path evenings run
status: todo
needs: [S3-R01, S3-R03]
touches: [mind/selection.py, mind/agents.py, app.py, scripts/evening.py, .env.example, tests]
---

# S3-R04 — One decision path: lean, aims and projects always on

## Why

`AI_LEAN`, `AI_AIMS` and `AI_PROJECTS` were Stage 1 experiments. Both entry points switch all three **on**
(`app.py` and `scripts/evening.py` read them with default `true`), so every live and headless evening runs
them on. But the core reads a missing key as **off** (`selection._flag`: `config.get(name, False)`), and almost
every test passes a config without them. So the suite specifies a decision path no evening takes.

Measured 2026-11-07 on a copy of the repo with the core defaults flipped to on: **23 cases fail**, 4,677 pass.
The player tasks will be written against the real path; the tests must run it first.

`AI_ANSWERS` stays a switch: it is off in production on purpose (D24) and the player will need that stage.

## Scope

- In: deleting `read_lean`, `read_aims`, `read_projects` and the off branches they guard; dropping the three
  keys from both configs, from the `run` section of `metrics.json` and from `.env.example`; the test edits below.
- Out: `read_answers`, `read_switch`, `read_temperature`. Any change to how lean, aims or projects behave when on.

## Approval

Test edits, **Approved by the owner, 2026-11-07**:

- Delete 6 test functions that specify the switches themselves:
  `tests/test_lean_requests.py`: `test_lean_requests_are_a_setting_of_the_config`,
  `test_the_lean_setting_is_read_from_the_config`, `test_a_lean_setting_that_is_not_a_bool_fails_loudly`;
  `tests/test_aim_choice.py`: `test_without_the_setting_no_aim_is_chosen`,
  `test_the_aims_setting_is_read_from_the_config`, `test_an_aims_setting_that_is_not_a_bool_fails_loudly`.
- Drop the now meaningless `"aims": True` / `"projects": True` / `"lean": ...` keys from test configs
  (`tests/test_aim_wiring.py:41`, `tests/test_projects.py:177`, `tests/test_aim_choice.py:36`, the helpers of
  `tests/test_lean_requests.py`).
- Adapt the 19 cases below to the on path, by the triage of step 2.

| File | Case |
|------|------|
| `test_agents.py` | `test_jev_success_uses_only_supplied_candidates`; `test_explicit_evaluators_score_the_decision[failure-falls-back-to-local]` |
| `test_facts.py` | `test_a_news_item_reaches_a_third_guest_in_other_words[seed-1]` |
| `test_families.py` | `test_a_flooded_choice_never_asks_about_more_than_the_limit[company]` |
| `test_gift_options.py` | `test_a_guest_who_decides_to_give_in_the_world_does_and_is_not_offered_it_again` |
| `test_intention_runners.py` | `test_a_quarrel_changes_the_targets_intention_and_then_their_choice` |
| `test_lockstep.py` | `test_partner_is_not_pulled_from_a_chat_by_a_late_answer`; `test_evening_runs_until_everyone_left_or_the_limit[everyone-leaves]`; `test_standing_without_an_action_is_logged_as_a_spell[instant-model, one-second-model, slow-model]`; `test_recorded_evening_replays_to_an_identical_event_log[every-call-answered, some-calls-fail]` |
| `test_seating.py` | `test_walking_out_needs_the_evaluators_endorsement[moderately-worthwhile-exit-may-be-drawn, clearly-best-exit-drawn]`; `test_only_options_close_to_the_best_are_drawn[close-second-is-sometimes-drawn]`; `test_jev_reads_a_briefing_instead_of_raw_maps`; `test_demo_newcomers_mostly_head_for_a_seat_or_the_tap` |
| `test_spread.py` | `test_a_hot_headed_drunk_sometimes_does` |

## Steps

1. **Red.** In `selection._flag`, make a missing `lean`, `aims` or `projects` read as `True` (temporary).
   Run `make test`: expect exactly 23 failing cases, the 19 of the table and 4 cases of the switch tests being
   deleted (`[aims-absent]`, `[absent-is-off]` twice, `[lean-requests-are-off-unless-the-config-asks]`). A
   different list means the code moved since 2026-11-07: update the table first.
2. **Triage, before editing any test.** For each of the 19 cases, run it alone (`-x -vv`) and add a row to a
   "Triage" section in this file: the failing assertion, the cause, the edit. Allowed edits, in this order of
   preference:
   - give the test a port the on path needs (an `aims` evaluator in its fake `Evaluators`, for instance);
   - change the test's inputs (the guest's needs, the room) so the behavior it names still shows on the on path;
   - change an expected value, stating old → new and why the new one is the same behavior.

   Never delete an assertion, loosen a comparison, or try seeds until one passes. A case that needs any of
   those: stop, write it in the triage table as "needs the owner", and leave the case failing on the branch.
3. **Green**, one commit (behavior change: the core path; approved test edits): delete `read_lean`, `read_aims`,
   `read_projects` and `_flag`'s use for them; in `agents.py` drop the three `if read_...(config)` guards so the
   on branch always runs (`choose_action` always adds `"projects": list(PROJECTS)`; `_aimed` always picks an
   aim for an `AIM_VERBS` action; `_decide` always makes a keyed request lean). Apply the triaged edits and the
   6 deletions.
4. **Refactor**, one commit: drop `lean`, `aims`, `projects` from the config in `app.create_default_app` and
   `scripts/evening.config`, from the `run` section in `scripts/evening.main`, and the three blocks from
   `.env.example`. Fix docstrings that still mention the settings (`grep -rn "read_lean\|read_aims\|read_projects\|AI_LEAN\|AI_AIMS\|AI_PROJECTS" backend scripts tests .env.example`
   must find nothing; `read_switch`'s own tests may keep `"AI_LEAN"` as a label only if renamed to `"AI_ANSWERS"`).

## Golden check

The entry points already ran the on path, so `events.jsonl` must be identical. `metrics.json` may differ only
by the three missing keys in `run`:

```bash
for d in runs/golden-base/*/; do n=$(basename $d); cmp $d/events.jsonl runs/golden-now/$n/events.jsonl; done
```

## Done when

- `make check` passes, or only the cases marked "needs the owner" fail and the PR says so.
- The golden `events.jsonl` files are identical; `metrics.json` differs only by the three `run` keys.

## Results

Filled in when the task is done.
