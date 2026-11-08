---
id: S3-02
title: Who steers a body
status: done
needs: []
touches: [backend/tavern/hall/player.py (new), backend/tavern/hall/state.py, backend/tavern/hall/world.py, backend/tavern/hall/rules.py, backend/tavern/adapters/persistence.py, backend/tavern/evening/scenario.py, backend/tavern/evening/lineup.py, backend/tavern/evening/decisions.py, backend/tavern/evening/mind_loop.py, backend/tavern/evening/player_commands.py (new), backend/tavern/mind/intentions.py, backend/tavern/social/turns.py, backend/tavern/social/conversation.py, backend/tavern/social/speeches.py, backend/tavern/social/stage_lines.py, backend/tavern/social/heckles.py, backend/tavern/server/runtime.py, frontend/src/types.ts]
---

# S3-02 — Who steers a body

## Why

Today models or scripts supply everything a guest does: Jev picks the decisions, Haiku writes the intentions,
the lines and the numbers on the stage, and a scripted line stands in whenever a model is late. A player needs a
body for which none of this is asked and no word is put in their mouth. They also need a switch that gives the
body back to the guest's own mind (autopilot) and takes it again. This task builds that core with no UI; when
it is done, a steered guest stands in the hall, and every scene they are in waits for them and then passes their
turn in silence.

## Scope

- In: `world.player`, `rules.player.silence`, `Scenario.player` and lineup's `player` argument; `steered`; the
  skips listed under Shape; the turn wait and the `silence` act; the `steer` command (autopilot); the snapshot
  type.
- Out: the body's commands (S3-03), the voice (S3-04), typing and the `ignored` thought (S3-05), the player's own
  number on the stage (S3-06), every screen (S3-07), the played guest coming in first (S3-07).

## Shape

- `hall/state.py`:
  ```python
  class Player(TypedDict):
      """The person playing tonight: which guest they play, and whether they hold the wheel."""
      actor_id: str   # an actor cast from one of the scenario's guests, never staff
      steering: bool  # True: the player decides for that guest; False: autopilot, the guest's own mind
  ```
  `World.player: Player | None`, which is None in an evening with no player (every evening today).
- `rules["player"] = {"silence": 20.0}`: real seconds. As with `conversation.turn_timeout`, a world at speed s
  waits `silence × s` game seconds. `check_rules` requires the key.
- `hall/player.py`, "The player: which guest they play, and whether they hold the wheel.":
  `steered(world, actor_id) -> bool`; `check_player(world)` for saves (raises `ValueError` when the actor is
  not one of the guests, present, expected or departed, or is staff, or the record is malformed).
- `evening/player_commands.py`, "The player's commands: check one and apply it to the world and the mind loop.":
  `steer(world, mind, command)` for `{"type": "steer", "on": bool}`. Taking the wheel overrules a pending
  decision (`MindLoop.overrule`), cancels a pending intention, and drops a claim on the guest's next line (the
  writer's answer is then discarded). Giving the wheel back lets the guest's mind decide again at once. Each
  switch logs a `steer` event naming the guest. The handler raises `ValueError` when the evening has no player
  or `on` is not a boolean. `TavernRuntime.command` routes `steer` to it.
- `Scenario.player: str | None = None`. `lineup_scenario(..., player)` checks that the player is one of the
  picked characters or None. `Lineup` takes a fourth argument, and `TavernRuntime._start` passes
  `command.get("player")`. `open_evening` sets `world.player = {"actor_id": <the actor cast from it>,
  "steering": True}`.
- What skips a steered guest: `decisions.free_to_decide` (no Jev decision); `intentions.intention_requests` (no
  intention; `stale_intentions` drops one in flight); `mind_loop._ask_answers` (no invitation answer);
  `turns.claim_turns` (no writer for their line); `stage_lines.stage_claims` and `speeches.perform_overdue` (no
  number, written or scripted: a steered performer stands on the stage until `give_speech` ends); and
  `heckles.heckler_of` (a steered guest is never picked as a heckler).
- The turn wait, in `turns.speak_turns`. When a steered guest's line is due and nothing is claimed or written for
  them, the scene speaks nothing for `rules.player.silence × speed` game seconds. Then it speaks a `silence`
  turn from them: act `silence`, line `"…"`, addressee None. The scripted writer is never asked for a steered
  speaker, at a timeout or anywhere else.
- `conversation.ACTS["silence"]`: its effect declines an invitation to the silent guest that is still waiting for
  an answer (`invitations.decline`). `offered_acts` never offers `silence` to a writer.
- Snapshot: `state.player` comes with the public world. In `frontend/src/types.ts`, add `Player`, set
  `WorldState.player: Player | null`, and add `{ type: "steer"; on: boolean }` to `Command`.
- Saves: version 24 (approved for Stage 3) carries `world.player` and `rules.player`; `parse_world` calls
  `check_player`.

## Tests that change

`test_database.py` pins the schema version: 23 → 24, the approved bump. No other test should change. In
particular, every golden evening has no player, so its log must not change.

## Steps

1. Baseline: `make golden GOLDEN=runs/golden-base`.
2. The record. Red first in a new `tests/test_player.py`: a parametrized `steered` block (no player, another
   guest, the played guest with the wheel, the played guest on autopilot) and a `check_player` error block
   (unknown actor, staff, steering not a boolean, a missing field). Then the type, the world field, the rules
   key, version 24 and the save check. Check: `pytest tests/test_player.py tests/test_database.py -x`.
3. The scenario: `tests/test_lineup.py` cases for a player among the picked guests, `None`, and one not picked
   (`ValueError`). Check: `pytest tests/test_lineup.py -x`.
4. The skips, one commit each, red first in that module's own test file, with a small hall that has a steered
   guest (`social_hall.py` helpers): no decision request, no intention request, no invitation answer asked, no
   claim on their line, no stage claim and no scripted number, and never a heckler. The same guest on autopilot
   is asked as before (one case each).
5. The wait: the steered guest's due line waits; at `silence × speed` a `silence` turn passes the turn on
   (parametrize speed 1 and 4); the invitation waiting on them is declined; a scripted line is never spoken for
   them. Check: `pytest tests/test_turns.py -x`.
6. `steer` through `TavernRuntime` with fake ports: taking the wheel discards the pending decision's answer and
   the writer's answer for their claimed line; giving it back starts a decision request on the next tick;
   errors are parametrized.
7. `types.ts`, then `make build`. Then the golden check.

## Done when

- `make check` and `make build` pass, output pasted in Results. The golden diff is empty.
- A lockstep evening of 300 s with one guest steered (a test or a throwaway script) gives that guest no
  decision, intention or written line after arrival. Results quote any `silence` turns it has; if no guest spoke
  to the steered one, say so.

## Results

**Check** (`make check`, after the last code change; `make build` ran on the final `types.ts`):

```
================== 4725 passed in ~200s ==================   (pytest)
ℹ tests 318 / ℹ pass 318 / ℹ fail 0                          (frontend node:test; the typecheck ran before it)
exit 0
make build: ✓ built in 4.63s, exit 0
```

**Golden:** `make golden GOLDEN=runs/golden-base` before the first edit and `GOLDEN=runs/golden-now` after the last
one: `diff -r runs/golden-base runs/golden-now` prints nothing.

**Lockstep, 300 s, Putin steered** (guests: Trump, Putin, Zelensky, Thatcher; a throwaway script, scripted writer,
offline local decisions, a fake intender; seeds 3, 1, 5 and 7): Putin got 0 decisions, 0 intentions asked and 0 lines
asked of a writer; the other three got 184 decisions, 17 intentions and 73 lines (seed 3). **No guest spoke to him
and he spoke in no scene, so there is no `silence` turn to quote**: the turn wait and the silence act are covered by
`tests/test_turns.py` (speed 1 and 4, the invitation declined).

**Tests that changed** (all the approved 23 → 24 bump): `tests/test_database.py` (the pinned version) and
`tests/test_intention_saves.py::test_new_worlds_are_version_23`, which the task did not list: its name and literal
became 24. One fixture, not an assertion: the `lineup=` lambda in `tests/test_lineup.py::runtime` takes the new fourth
argument (`player=None`), because `Lineup` now has four.

**Deviations and notes**
- `Lineup` is `(cast, ids, minutes, player)` as the task says; `lineup_scenario`'s `player` defaults to None so its
  other callers are untouched.
- `heckles.heckler_of` now takes `(world, performer, target_id, listeners)` instead of `now`: it needs the world to
  ask `steered`. Its only caller is `speeches.perform`.
- `silence` sits in `conversation.ACTS` (effect `invitations.decline`), so the Haiku writer's prompt table and schema,
  which `test_acts_and_their_meanings_come_from_the_table` pins to the whole of `ACTS`, now list it; its meaning
  says never to choose it, and `check_turn` refuses it anyway (`offered_acts` never offers it). Filtering it out of
  the prompt would change that test: a follow-up for the owner's call.
- A silent turn is logged and kept in the scene's `turns`, but makes no sound and is neither noted for aims, heard,
  nor overheard (nothing was said).
- The wait also holds when a claim is outstanding for a steered speaker, so the scripted timeout never speaks for them.
- The played guest is not yet first in (S3-07); `world.player` is set at opening even while they are still expected.
