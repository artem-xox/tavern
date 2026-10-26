---
id: S2-17
title: Walk up to someone standing
status: todo
needs: [S2-16]
touches: [backend/tavern/body/actions.py, backend/tavern/hall/routes.py, backend/tavern/hall/sight.py, backend/tavern/social/walk_ups.py (new), backend/tavern/evening/decisions.py, backend/tavern/body/expression.py, backend/tavern/mind/agents.py, backend/tavern/mind/local_policy.py, backend/tavern/mind/options.py, backend/tavern/body/activities.py, backend/tavern/body/projects.py, tests/test_approach.py]
---

# S2-17 — Walk up to someone standing

## Why

After [S2-16](16_standing_talk.md) two guests who happen to stand near each other can talk, but such meetings are
rare and short (1–2 seconds on `main`: an idle stander decides about once a second and walks off). A guest who
wants company can walk over only to someone *seated* at another table (`approach`). After this task they can also
walk up to someone standing (at the darts, by a window, in a standing chat) and start or join a conversation there,
and the one they walk up to waits for them instead of wandering off.

## Scope

- In: `approach` to a guest who stands in the open; that guest waits and turns to the walker; candidates, local
  score, option sentence and wording; a rematch project that walks up to a standing winner.
- Out: following someone who walks (a walker is not offered and is refused); stopping a walker in passing; the
  `closes_in` verbs (helping up, stepping between fighters, asking a healer), which still need a table; waiting
  for someone who walks over to your table (seated partners keep today's rules).

## Shape

- Same verb, `approach`; no new verb or family. Where the partner is decides the way:
  - at a table (`scenes.at_table`, seated or standing at its spot): today's rules, routed by that table's free
    spots (use `at_table`, not the seat's table, in `routes._approach_plan`);
  - standing in the open (no table): route to a free cell next to them (Chebyshev 1), else within
    `rules.conversation.reach`, nearest by walking; a cell must be walkable, not occupied or reserved, and
    `side_by_side` with the partner from it (no wall between).
- `actions._approach_error`, new refusals for a partner standing in the open, at the start: on the move
  (`status` walking or a path left): "{name} is on the move"; already within reach: "{name} is right beside them:
  talk instead". On arrival, out of reach: "{name} walked off". Staff, sleepers, the fallen, fighters, a pressed
  partner and a full scene are refused as today.
- Arrival: `_approach_scene` already starts a scene or joins the partner's; with S2-16 the scene is a standing one.
- Observation: each `people` entry gains two public fields, not saved, not in the snapshot, not printed by the
  briefing: `walking: bool`, True while they are on their way (`status` walking or waiting, or a path left);
  `at_table: str | None`, the table they are at, seated or standing by it (`scenes.at_table`). `table_id` keeps
  meaning the seat's table: many callers pair it with `seat_id`.
- New module `social/walk_ups.py`, "Someone walking up to a guest who stands in the open, and the guest waiting
  for them": `walker_toward(world, actor_id) -> Actor | None`, the guest whose `approach` (key off
  `ACTIVITIES[verb].approaches`, not the verb's name) targets them while the walker is `walking`, or `waiting` with
  `_blocked_for` under `rules.long_wait`, and while the target stands in the open and no need presses on them
  (`scenes.pressed`). Derived from the world each time: no new saved field.
- `decisions.free_to_decide` is False while `walker_toward` names someone: the target asks for no decision, so
  they are not counted as stalled (`lockstep` uses the same rule). `expression._focus`: a guest in no scene and
  with no target of their own faces their walker.
- `agents._social_candidates`, a walk-up is offered to someone not near, with no seat and no `at_table`, not
  `walking`, not staff (`post`), who is either in a `conversation` or `available` and visibly doing something
  where they stand (`doing` set: darts, a window, the bar, a line). One per conversation, else one per person.
  An idle stander with nothing to do is not offered: they are about to decide and move off. A stander at a table's
  spot is reached through that table, as today. The world still accepts a walk-up to an idle stander.
- `local_policy._score_approaches`: the walk cost is `steps_to` the person when they sit at no table.
- `options._approach`, for a partner without a seat: "walk {walk words} over to {name}{pale}, who is {their
  activity's `doing`, as `briefing._person` words it}, and talk with them on their feet". Seated partners keep
  today's sentence.
- Wording in `activities.py`: `approach.what` "walk over to {target}, to the table where they are or to where they
  stand, and talk with them"; `approach.guidance` adds "or someone standing about the room"; `FAMILIES["company"]`
  "... walk over to someone at another table or standing elsewhere, ...". The `approaches` attribute's docstring
  says both ways. These texts reach Jev: say so in the PR.
- `projects._reach`: walk up to a standing winner too (an `approach` when they are at a table or stand still).

## Tests that change, because the behaviour they pin is what this task replaces

- `test_approach.py::test_an_approach_is_refused[a-partner-who-stands]`: Cid stands in the open; an approach to
  him is now accepted. The case leaves the refusal block; the acceptance is covered by step 2's new test.
- No other. The unseated guests in `test_approach.py::evening()` stand idle with nothing to do, so the candidate
  tests there keep their lists. If any other test changes, stop and report it.

## Steps

1. People see who is on the move and where they stand: red test on `observe_people` (`walking` and `at_table` for
   an idle stander, a walker, a guest blocked mid-route, a guest seated, a stander on a table's spot), then
   `sight.people_in_sight`. Check: `pytest tests/test_world.py -x`.
2. The world: in `tests/test_approach.py`, red tests that an approach to a stander in the open ends in a standing
   scene with the walker next to them (and joins a standing scene of theirs), and a refusal block with the three
   new reasons plus `a-wall-between-every-free-cell`. Then `_approach_error`, `routes._approach_plan`. Check:
   `pytest tests/test_approach.py -x`.
3. The wait: red tests that a stander walked up to is not `free_to_decide`, faces the walker, and is free again
   once the walker arrives, gives up, is blocked for `long_wait`, or a need presses on them. Then `walk_ups.py`,
   `decisions.py`, `expression.py`. Check: `pytest tests/test_decisions.py tests/test_expression.py -x`.
4. The mind: candidate cases for standers (`at-the-darts` offered, `idle` not, `walking` not, `staff` not,
   `asleep` not, `at-a-tables-spot` not, two in one standing scene give one walk-up), the score (walk cost to the
   person; the lonelier walk over more readily, as for tables), the option sentence, the wording. Check:
   `pytest tests/test_approach.py tests/test_families.py -x`.
5. The rematch walks up to a standing winner: a red case in `tests/test_rematch.py`, then `projects._reach`.
6. `make check`; the offline, live and replay evenings as in S2-16, against S2-16's numbers.

## Done when

- `make check` passes, output pasted in the PR.
- Offline Guests seeds 1, 2 and 5: count walk-ups to standers that ended in a scene and those that failed (by
  reason). More end in a scene than fail; record both, and the scenes and stuck seconds against S2-16's.
- One moment from a live log in Results: a guest walking up to someone at the darts or by a window, and what
  they said.

## Results

Filled in when the task is done: what was built, the numbers, one moment from a log.
