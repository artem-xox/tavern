---
id: S3-13
title: What the body may do
status: done
needs: [S3-03, S3-08]
touches: [backend/tavern/evening/player_commands.py, backend/tavern/hall/world.py, backend/tavern/body/projects.py, tests/test_player_hands.py]
---

# S3-13 — What the body may do

## Why

Playtest bug: the played guest could not sit at tables. `options` listed `candidates.open_actions`, the NPC
mind's curated wishes, which hide seats on purpose: a targetless `seating` wish until the guest owns a seat, then
only their own `favorite_seat_id`. A click on a stranger's free chair or on a table therefore showed "Nothing to do
here now". A person at the wheel should be offered what the body may do, not what the guest's mind would want.

## Scope

- In: `options` for the played guest; a dry-run check of `start_action`.
- Out: NPC candidates (unchanged, so the golden evenings do not move); the frontend (the menu already names
  chairs by their object name); clicking oneself for targetless verbs.

## Shape

- `hall/world.py` `start_refusal(world, actor_id, action) -> str | None`: the reason `start_action` would give,
  without changing the world (staff, project, cut-in, `action_error`, last call, a reachable spot unless the
  guest waits in line). `start_action` shares its checks (`_visitor_refusal`, `_checked`): a pure refactor.
- `projects._project_error` becomes `project_error`, which `start_refusal` uses.
- `player_commands.options`: the mind's list for the target, plus every verb the body may start there now
  (`start_refusal` is None). A table counts with what stands at it (objects whose `table_id` is the table), so a
  click on a table offers its free chairs. An item-naming verb is tried with each item in hand. Decision steps
  (`duration` None), plans (`opens_project`), `walk_to` and staff verbs stay with the mind's list and the floor
  click. A `cut_in_line` nobody waits in is the plain use of the place, already listed, so it is dropped.

## Results

- Red, then green: `test_options_offer_every_free_chair_the_played_guest_may_sit_in` (own seat, a stranger's free
  chair, a free chair before owning a seat, a taken chair, a table with two, one or no free chair),
  `test_sitting_in_a_strangers_chair_from_the_options_makes_it_the_guests_seat`,
  `test_options_offer_what_the_body_may_do_though_the_guest_does_not_want_it` (the tap when not thirsty).
- Widened for the player (what the mind hides from itself): any free table chair, and `rest` on it; the tap
  when not thirsty; darts, the toilet, any window and the fireplace whatever the needs; leaning on the bar with no
  barkeep in sight; `approach` to anyone, liked or not; `talk`, `join_conversation`, `give` (each item in hand),
  `bring_drink`, `shove` and `fight` with anyone the body can reach; the stage's `give_speech` when the world allows it.
- A first try added an `Activity.table_chair` rule (rest only on a chair apart from a table). It broke
  `test_giving.py::test_a_guest_resting_on_a_chair_reaches_those_seated_at_its_table`, which specifies resting on a
  table chair, so it was dropped: a chair click offers both "Rest" and "Sit at a table".
- Golden diff empty; `make check` and `make build` pass (output in the PR).
