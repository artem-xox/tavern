---
id: S3-10
title: A scripted player
status: todo
needs: [S3-03, S3-04]
touches: [backend/tavern/evening/player_script.py (new), backend/tavern/evening/player_commands.py, backend/tavern/evening/lockstep.py, backend/tavern/evening/report.py, backend/tavern/evening/player_metrics.py (new), backend/tavern/server/runtime.py, scripts/evening.py, Makefile, data/players/ (new)]
---

# S3-10 — A scripted player

## Why

Every check of an evening is headless (`make evening`, `make golden`, replays), and none of them has a player.
Without one, the player's path is tested only in unit tests and by hand. A scripted player is a timed list of
the commands a person would send. It plays the same code (principle 5), its readings are recorded and replayed
like every other model call, and the golden check then guards the player's path in later refactors.

## Scope

- In: the script format and its parser; one dispatcher for the player's commands, shared by the runtime and the
  lockstep; `--player-script` for `scripts/evening.py`; a fifth golden evening; `player` in `metrics.json`; two
  sample scripts.
- Out: a scripted player that decides from what it sees (a bot); acceptance itself (S3-12).

## Shape

- A script, `data/players/<name>.json`:
  ```json
  {"player": "monroe", "steps": [
    {"at": 20.0, "command": {"type": "act", "action": {"id": "take_beer:tap-1", "verb": "take_beer", "target_id": "tap-1"}}},
    {"at": 45.0, "command": {"type": "say", "text": "Vladimir, darling, you look lonely.", "to": "auto"}}
  ]}
  ```
  `at` is in game seconds and never decreases from step to step. `command` is any player command the client sends
  (`steer`, `act`, `say`, `typing`), never `options`.
- `evening/player_script.py`, "A scripted player: timed player commands for a headless evening.":
  `parse_player_script(data) -> PlayerScript` (a frozen dataclass: `player: str`, `steps: tuple[Step, ...]`).
  It raises `ValueError` naming the bad value for an unknown command type, an `at` that is not a number or goes
  back in time, a missing field, or an extra field.
- `player_commands.apply_command(world, mind, command)` routes `steer`, `act`, `say` and `typing` to their
  handlers. `TavernRuntime.command` routes those four types here, and the lockstep calls it for each step that is
  due at the tick it falls in, before `mind.tick`.
- A refused step logs a `control` event ("Player script: <type> refused: <reason>") and the evening goes on, so a
  script survives an evening that took another course.
- `scripts/evening.py --player-script PATH` makes the script's player the scenario's `player`.
  `make evening PLAYER=data/players/monroe_meddles.json` passes it on.
- `make golden` plays a fifth evening, Guests seed 5 with `data/players/monroe_meddles.json`, offline. Its first
  run is the new baseline.
- `metrics.json` gets `player` (`evening/player_metrics.py`, from event fields): `actor`; `lines` by act (from
  `turn` events with `player: true`); `misread`; `silences`; `ignored` (S3-05's events, 0 before it); `actions` by
  verb (`player_act`); `refused` (script refusals). The section is absent in an evening without a player.
- Sample scripts: `monroe_meddles.json` (Guests: Monroe works the room, flatters Putin, insults Trump, invites
  someone to darts, climbs the stage) and a short `locals_smoke.json` for the Locals cast.

## Steps

1. The parser. Red first: one block of good scripts (`empty-steps`, `one-say`, `same-at-twice`) and one error
   block (`unknown-type`, `options-step`, `at-goes-back`, `at-not-a-number`, `missing-command`, `extra-field`,
   `not-a-mapping`). Check: `pytest tests/test_player_script.py -x`.
2. `apply_command`: a refactor of the runtime's routing first (golden unchanged), then a test that each command
   type reaches its handler's effect on a small hall.
3. The lockstep: a test with a fake courier where a two-step script runs its steps at their ticks; a refused step
   is logged and the run goes on.
4. Metrics: red first, a hand-made event list in, the `player` section out; with no player, no section.
5. The script flag, `make evening PLAYER=…`, the samples, and the fifth golden evening.
6. Evenings: offline (`--mode local --writer scripted`), live with `.env`, and its replay
   (`MODE=replay CALLS=…`). `cmp` the live and replay `events.jsonl`.

## Done when

- `make check` passes, output pasted in Results.
- The live and replay `events.jsonl` of step 6 are identical. Results paste the `player` section of the live
  run and one moment where a guest answers a scripted line.
- `make golden` plays five evenings, twice in a row with an empty diff.

## Results
