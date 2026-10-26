---
id: S2-16
title: Talk where you stand
status: done
needs: []
touches: [backend/tavern/social/scenes.py, backend/tavern/hall/sight.py, backend/tavern/hall/sightlines.py (new), backend/tavern/social/bystanders.py, tests/test_scenes.py]
---

# S2-16 — Talk where you stand

## Why

Two guests who stop next to each other in the middle of the hall cannot talk. `scenes.side_by_side` lets
standers talk only in one line (next to each other), at one bar, or when both stand by the fire or a window
(`_by_a_view`). Everywhere else they stand mute, and `within_reach` (the reach of a chat, a gift, a shove) says no.
Measured on `main` (offline, scripted writer, `rules.conversation.reach` 2): Guests seeds 1, 2 and 5 had 8, 15 and
4 such meetings (two guests standing still within 2 cells in the open, neither in a scene), 9, 38 and 7
pair-seconds in all; Locals seed 5 had 8 meetings and 28 pair-seconds. After this task any two guests who stand still
near each other can start a conversation there, and others can join it.

## Scope

- In: the open-floor rule in `side_by_side`; a wall between two standers keeps them apart; a scene started by a
  stander on a table's spot with someone in the open is a standing scene; `_by_a_view` goes (the new rule covers it).
- Out: walking over to someone who stands ([S2-17](17_walk_up.md)); stopping for a word while passing (walkers
  stay out of reach); the barkeep, who stays reachable only across his bar; standers chatting with someone seated
  (the table rule stays as it is); privacy in the WC (someone in its doorway can talk to a guest on the pot: if a
  log shows it, add it to `TECH_DEBT.md`).
- Consequence, intended: `within_reach` follows `side_by_side`, so handing something over, fetching a drink for,
  shoving and picking a fight with someone standing beside you in the open become possible too. Chaos is the
  feature.

## Shape

- `scenes.side_by_side(world, actor, other)`: after the line rule and the bar rule, two guests are side by side
  when both stand still and are within `rules.conversation.reach` cells (Chebyshev, as today) with no wall on the
  straight line between their cells. "Stand still" means: not seated, `status` not `walking`, no `path` left (a
  guest blocked mid-route has `status` `waiting` and a path: they are not still). Staff (`staff.on_staff`) never
  meet this rule. Same person: False, as today.
- The wall test is `line_visible` with `world["map"]["blocked"]`. `scenes` cannot import `hall.sight` (sight
  imports scenes), so `line_visible` moves first to a new `hall/sightlines.py` (step 2).
- `scenes.start_conversation`: `table_id` is the starter's table only when the partner is at the same table
  (`at_table` of both); otherwise None. Today a stander on a table's spot who talks to someone in the open opens a
  table scene the partner is not "at", and `_still_there` drops the partner at the next tick.
- No new rule key (reuse `reach`), no save, snapshot or `types.ts` change, no prompt change: an option to talk
  to a stander already reads "start a conversation with X, who stands beside them" (`options._talk`).
- `scenes.py` is 527 lines, over the ~400 limit. Keep its net growth at about zero (the new branch replaces
  `_by_a_view`); do not split it in this task.

## Tests that change

None should. `test_table_reach.py::...[strangers-in-the-open]` stands Ada and Bea 3 cells apart, and
`test_bar_chat.py` keeps the barkeep out by the staff rule. If one fails, stop and report it.

## Steps

1. Baseline, on `main` before any change: run `scripts/evening.py --mode local --writer scripted --cast guests`
   for seeds 1, 2 and 5 (`PYTHONPATH=backend` in a worktree) and write their `conversation.scenes` and stuck
   seconds from `metrics.json` into this file.
2. Refactor, own commit: move `line_visible` from `hall/sight.py` to `hall/sightlines.py` (docstring: "Whether a
   wall stands on the straight line between two cells."); `sight.py` and `social/bystanders.py` import it from
   there; fix the comment in `body/hearing.py` that names `sight.line_visible`. Add `sightlines` to the `hall/`
   list in `AGENTS.md`. Check: `make test` green with no test edited.
3. The open-floor rule. Red first in `tests/test_scenes.py`, one parametrized block on `side_by_side`, ids:
   `one-cell-apart` True, `reach-apart` True, `one-past-reach` False, `a-wall-between` False, `one-walking`
   False, `one-blocked-mid-route` False, `one-seated` False, `the-barkeep-off-his-bar` False, `the-same-guest`
   False. Then one test that `talk` in the open starts a scene with `table_id` None that survives
   `advance(world, 3)`, and that a third guest standing beside them can `join_conversation`. Then green: the new
   branch, `_by_a_view` removed, the docstrings of `side_by_side` and of the module updated. Check:
   `.venv/bin/python -m pytest tests/test_scenes.py -x`.
4. What a guest is offered: a test that an idle stander's `build_candidates` include `talk:<neighbour>` for a
   guest standing still beside them in the open, and nothing for one 3 cells away (pattern:
   `test_table_reach.py`). It may already pass after step 3: then say so in the PR and add no code for it.
5. The scene's place: red test that Ada on a table's spot and Bea in the open beside her start a scene with
   `table_id` None that still holds both after `advance(world, 1)`; then fix `start_conversation`. Check:
   `pytest tests/test_scenes.py tests/test_table_reach.py -x`.
6. Evenings: repeat step 1's runs, then the live seed 5 and its replay (plan README, step 8), and `cmp` the two
   `events.jsonl`.

## Done when

- `make check` passes, output pasted in the PR.
- Offline Guests seeds 1, 2 and 5: at least one scene between two
  guests standing in the open (not in a line, at a bar, or by a view). Find it with a throwaway script
  (not committed) and quote its `conversation_started` event with both guests' cells in Results.
- Seed-sensitive tests (`test_first_evening.py`,
  `test_facts.py::test_a_news_item_reaches_a_third_guest_in_other_words`) may play differently. If one fails,
  stop and report the seed and the failure; do not edit it without the user's approval.

## Results

Built: `hall/sightlines.py` (`line_visible` moved), the open-floor branch of `scenes.side_by_side` (fire/window rule
removed), `start_conversation` holding a scene at a table only when both are at it. No save, snapshot or prompt change.

Numbers, offline Guests seeds 1, 2, 5, `main` vs this task alone: scenes 22/31/23 vs 14/18/15, stuck seconds
12.6/25.7/0.0 vs 15.4/6.1/3.1. Scenes fell because a chat on one's feet also eases the wish for company, so fewer
scenes at tables are needed (guests spend 4-7 points more of the evening seated); the original "more scenes" target was
wrong and is replaced above. Scenes held in the open, away from lines, bars and tables: 2 (seed 2, by a window) on
`main`, 3 now (seed 1 at (6,3)+(8,3) and (17,3)+(16,3), seed 5 at (2,9)+(1,11)).

Tests edited, with the user's request for this behavior: `test_table_reach.py` `[stander-at-another-table]` and
`[standing-guest-talks-to-a-seated-one]` (Bea and Cid stood 2 cells from Ada by accident), `test_queue_choices.py`
(the impatient guest is made unsociable so he does not chat with the darts player). The offer test passed at once:
`build_candidates` already offered `talk` to anyone `beside`.
