---
id: S3-03
title: The player's hands
status: todo
needs: [S3-01, S3-02]
touches: [backend/tavern/body/activities.py, backend/tavern/body/actions.py, backend/tavern/hall/lifecycle.py, backend/tavern/hall/world.py, backend/tavern/mind/candidates.py, backend/tavern/evening/player_commands.py, backend/tavern/adapters/persistence.py, backend/tavern/server/runtime.py, backend/tavern/server/api.py, frontend/src/types.ts, AGENTS.md]
---

# S3-03 — The player's hands

## Why

The player must be able to do whatever a guest does: walk across the hall, pour a beer at the tap, sit, drink,
play darts or dice, climb the stage, give something, shove someone. The world already validates every verb
(`start_action`), and `candidates` already lists the actions open to a body right now. The player is missing
three things: a command that names an action for their own body, a way to ask what is open, and one verb no
guest needs, which is to walk to a spot on the floor and stand there.

## Scope

- In: the `act` and `options` commands; the `walk_to` verb; the `player` decision source.
- Out: the click and the menu in the client (S3-08); talking, which is `say` (S3-04). The talk verbs themselves
  (`talk`, `approach`, `join_conversation`) are ordinary options here: they open or join a scene, and the
  player's first line is then up to S3-04.

## Shape

- Command `act`: `{"type": "act", "action": {"id", "verb", "target_id"?, "item"?, "cell"?}}`. The handler
  `player_commands.act` starts the action for the played guest with `start_action` and sets their `decision`
  to `{"source": "player", "scores": {}, "error": None}`, so the inspector shows who chose it. It raises
  `ValueError` (the client gets `{"type": "error", "message"}`) when the evening has no player, the guest is
  on autopilot or not in the hall, or the world refuses; the message is the world's `reason`. An action that
  takes the player away from their scene ends their part in it through the scene's own rule
  (`scenes._still_there`); nothing new is needed for that.
- Command `options`: `{"type": "options", "target_id"?: str}`. Its reply is
  `{"type": "options", "target_id": str | null, "options": [{"action": Action, "label": str}]}`: the played
  guest's concrete legal actions, restricted to those on `target_id` when one is given. `label` is the verb's
  `client_activities` label. The reply leaves the world as it is, apart from the knowledge refresh that
  `observe_actor` already does for every decision. `candidates._concrete_candidates` becomes public as
  `open_actions(observation)`, because the handler imports it. `TavernRuntime.command` returns the reply,
  and `api._serve_socket` sends it before the snapshot.
- Verb `walk_to`: `Action.cell: list[int]` (`[x, y]`), id `walk_to:<x>,<y>`. Its target is a cell where one may
  stand: inside the hall, not blocked, not off limits (`staff.off_limits`), and reachable by `find_path`. The
  walker routes there and ends idle on that cell, standing, not seated. A refused cell gets a reason
  ("Nobody can stand there", "No way there"). `Activity` gets one field for it: `to_cell: bool = False`.
- `walk_to` is for the player only, so no candidate rule offers it, and it has no local utility or option
  sentence. AGENTS.md's verb recipe gets one line on this exception.
- Saves: an action's `cell` is checked by `parse_world` (the next schema version, approved for Stage 3).
- `act` and `options` are not logged as "Operator: …" events. An accepted `act` logs one `player_act` event with
  a `verb` field (fields, not wording: R06), so that metrics and the story can tell what the player chose.
  Refusals go to the client only.
- `types.ts`: `Action.cell?: [number, number]`; `Command` gets `act` and `options`; a new `OptionsMessage`.

## Steps

1. `walk_to`. Red first: one parametrized block on accepted cells (`next-to-the-walker`, `across-the-hall`, the
   walker's own cell) that run to idle on that cell; one on refusals with `pytest.raises` or the refusal
   reason (`a-wall`, `behind-the-bar`, `outside-the-hall`, `cut-off`, `malformed-cell`). Then the verb.
   Check: `pytest tests/test_walk_to.py -x`.
2. The saved `cell`: a `test_persistence` case for an action with a good cell, and one rejecting a cell off the
   map; then the version. Check: `pytest tests/test_persistence.py tests/test_database.py -x`.
3. `act`. Red, through `player_commands.act` on a small hall: an accepted `take_beer` starts with source
   `player`; the error cases in one block (no player, on autopilot, not yet arrived, an action the world
   refuses, malformed). Check: `pytest tests/test_player_commands.py -x`.
4. `options`. Red: a played guest next to the tap is offered `take_beer`; with `target_id` set to another
   guest, only verbs aimed at that guest; with no player, `ValueError`. Then the socket: a FastAPI `TestClient`
   test sends `options` and gets the reply, then the snapshot.
5. `types.ts`, then `make build`.

## Done when

- `make check` and `make build` pass, output pasted in Results.
- The socket test of step 4 walks the played guest to a cell, then makes them take a beer and drink it, all
  through `act`.

## Results
