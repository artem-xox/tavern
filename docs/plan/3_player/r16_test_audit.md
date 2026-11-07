---
id: S3-R16
title: Delete tests that pin wording, data or a tuning number, and merge same-shape twins
status: todo
needs: [S3-R00]
touches: [tests]
---

# S3-R16 — Test audit

## Why

The suite is mostly good: 4,700 cases, behavior-named, parametrized with ids, no mocks, no
`monkeypatch.setattr`, no private imports (checked 2026-11-07). What wastes it is narrower than it looks:

- R03 and R04 remove the tests of removed features and switches.
- R15 removes copied helpers.
- What is left is below: tests that do not specify a behavior, so they break on any rewording or re-layout
  and protect nothing a player would notice. AGENTS.md: "A test that fails under a pure refactor is a bad test."

## Rubric

Delete a test only if it matches one row; anything else stays.

| Kind | Rule | Keep instead |
|------|------|--------------|
| **Wording pin** | asserts a phrase is (or is not) in prompt text or a constant, with no behavior behind it | a test that the text is *used*: the prefix reaches the question, stays byte-stable, stays over 4,096 tokens |
| **Data pin** | asserts the content of `data/tavern.json` (positions, counts, names, appeal values) rather than a rule over it | rule tests with a hand-made hall |
| **Tuning pin** | asserts a tuning constant equals a literal | the behavior the number produces |
| **Twin** | two tests in one file with the same body and assertion shape, differing only in cases | one test, the cases merged into its `parametrize` list, ids kept |

## Candidates (owner decides each row)

| Test | Kind | Note |
|------|------|------|
| `test_story_tavern.py::test_text_a_player_or_model_reads_names_the_story_tavern` | wording | a rename guard from S2-00 ("Last Inn" not in text); the rename landed 2026-10-17 |
| `test_story_tavern.py::test_the_prefixes_place_the_tavern_between_worlds_and_keep_the_locals` | wording | |
| `test_story_tavern.py::test_the_prefixes_let_famous_guests_talk_about_their_own_public_life` | wording | |
| `test_story_tavern.py::test_the_prefixes_say_famous_guests_know_one_another` | wording | |
| `test_story_tavern.py::test_the_news_of_the_day_names_the_wars_and_the_date` | wording | pins "OCTOBER 2026" in `WORLD_NOW`, which must be refreshed (its own comment says so) |
| `test_story_tavern.py::test_the_line_writer_may_discuss_the_news_of_the_day` | wording | |
| `test_story_tavern.py::test_the_line_writer_plays_famous_guests_for_laughs` | wording | |
| `test_story_tavern.py::test_a_new_scene_never_opens_on_the_road` | wording | over `scenes.TOPICS` |
| `test_evening.py::test_demo_inn_has_five_identical_two_seat_tables` | data | |
| `test_evening.py::test_only_the_hearth_table_of_the_demo_inn_is_appealing` | data | the appeal *rule* is `test_seat_appeal_comes_from_nearby_windows_and_fireplace` |
| `test_world.py::test_demo_layout_contains_three_visitors_and_valid_objects` | data | asserts 20 × 14 and 3 actors |
| `test_hall_layout.py` (6 tests) | data | fireplace, darts, windows positions; keep `test_the_hall_is_walled_all_round` if the owner sees it as a rule |
| `test_speeches.py::test_a_speech_is_fun` | tuning | `ACTIVITIES["give_speech"].fun == 0.8` |
| `test_agents.py::test_candidates_reject_malformed_observations` + `::test_malformed_actor_or_reservation_is_not_silently_ignored` | twin | same body; merge into the first |
| `test_jev.py::test_invalid_candidates_fail_before_request` + `::test_malformed_action_shapes_are_rejected_before_request` | twin | same body; merge into the first |

Keep, though they look similar: `test_story_tavern.py::test_most_line_examples_voice_famous_guests` (a
measured property with its live evidence) and `::test_the_prefixes_give_famous_guests_the_news_of_the_day`
(the news block is wired into both prefixes). Content validation of the character catalog
(`test_character_catalog*.py`, `test_famous_cards.py`, `test_recent_news.py`): data the game cannot run
without, kept.

## Approval

**Approved by the owner, 2026-11-07: every row as written.** Every wording, data and tuning row is deleted and
both twins are merged. In `test_hall_layout.py` the row's own exception holds: `test_the_hall_is_walled_all_round`
stays, the other five go. The "Keep" list above stays.

## Steps

1. One commit per file: delete the approved tests; merge the approved twins (case lists concatenated, ids
   unchanged, the merged test keeps the first name). Remove helpers and imports left unused.
2. Paste the case count before and after; the difference must equal the deleted cases exactly.
3. Add the rubric (four lines) to AGENTS.md under "Testing", so new tests do not reintroduce pins.

## Done when

- `make check` passes. Pasted into Results with both case counts.

## Results

Filled in when the task is done.
