---
id: S3-07
title: Take the wheel
status: todo
needs: [S3-02]
touches: [backend/tavern/evening/scenario.py, frontend/src/lineup.ts, frontend/src/lineupscreen.ts, frontend/src/wheel.ts (new), frontend/src/wheelbar.ts (new), frontend/src/rolesheet.ts (new), frontend/src/scene.ts, frontend/src/main.ts, frontend/src/style.css, frontend/src/types.ts, frontend/tests/]
---

# S3-07 — Take the wheel

## Why

After S3-02 the world knows a player, but nobody can become one: the lineup screen has no "Play as", the hall
does not show which guest is yours, and there is no button for autopilot or pause. This task makes the evening
playable as a body (the hands and the chat follow in S3-08 and S3-09). It also gives the player a cheat sheet for
the role, because the owner chose a sheet from the card over checked goals.

## Scope

- In: "Play as" on the lineup screen; the played guest comes in first; the "you" marker; the wheel bar
  (face, name, a You / Autopilot switch, Pause / Resume); the role sheet.
- Out: clicks that act (S3-08); the chat (S3-09); a card of one's own (not in this stage).

## Shape

- Lineup screen. Below the picked faces, a "Play as" row offers "Just watch", the default, and each picked guest.
  `startCommand(cast, picked, minutes, player)` sends `player: string | null`. Putting back the face of the
  guest picked to play resets the choice to "Just watch". Pure logic goes in `lineup.ts`.
- The played guest comes in first. With a `player`, `open_evening` lets the played guest in at the first second
  of `opening_window`, and the others in a random order after them, as today. Without a player, the order is
  unchanged (golden).
- `wheel.ts` (pure): `wheelState(snapshot) -> {face, name, steering, paused, present} | null`, which is null with
  no player. `wheelbar.ts` draws it above the hall: the switch sends `steer`, the button sends `pause`, and Space
  sends `pause` too when no text field has focus. The debug panel stays as it is.
- The "you" marker: a small arrow above the played guest's head that follows them, drawn the same way whether the
  guest is steered or on autopilot. A pure function decides where it goes and is tested in `heading.test.ts`
  style; Phaser only draws it.
- `rolesheet.ts` (pure, plus a small panel that can be folded away): from the played guest's card and ties in the
  snapshot, it lists the persona, the obsessions, the catchphrases, and the rivals (ties with a grudge or a
  negative opinion), each with their name. Nothing is checked or scored.
- `types.ts`: the `start` command gets `player: string | null`.

## Steps

1. Backend: a `test_scenario` case where the played guest arrives first and the others keep the seeded order;
   one where there is no player and the order is unchanged. Check: `pytest tests/test_scenario.py -x`; golden
   unchanged.
2. `lineup.ts`: in `frontend/tests/lineup.test.ts`, the start command carries the player; a removed pick resets
   it; the player must be one of the picked guests. Check: `npm --prefix frontend test`.
3. `wheel.ts` and the marker's placement, tested; then `wheelbar.ts`, the marker and the Space key.
4. `rolesheet.ts`, tested on a hand-made card (no persona, no ties, several rivals); then the panel.
5. `make check`, `make build`, then a run.

## Done when

- `make check` and `make build` pass, output pasted in Results.
- With `make run`: pick Guests, pick Monroe, Putin and Trump, play as Monroe. Monroe comes in first, under the
  marker. The switch moves the inspector's decision source between `player` and Jev or local; Space pauses and
  resumes; the sheet shows Monroe's obsessions. Screenshots in Results.

## Results
