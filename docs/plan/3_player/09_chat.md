---
id: S3-09
title: The chat
status: in-progress
needs: [S3-04, S3-05, S3-07]
touches: [backend/tavern/social/player_lines.py, backend/tavern/server/runtime.py, frontend/src/chat.ts (new), frontend/src/chatpanel.ts (new), frontend/src/connection.ts, frontend/src/main.ts, frontend/src/style.css, frontend/src/types.ts, frontend/tests/chat.test.ts (new)]
---

# S3-09 — The chat

## Why

S3-04 and S3-05 make the player's lines work in the world, but the player still has no place to type them, no
view of what was said in their scene, and no sign that the scene is waiting for them. This task adds the chat:
the lines of the player's scene, an input, the "To:" picker, a "your turn" sign with the time left before the
turn passes, and typing pings that hold the turn.

## Scope

- In: the panel; the snapshot's `player_turn`; the typing pings; the stage mode, when S3-06 is merged.
- Out: speech bubbles, which already show every line, the player's included; a log of the whole evening (the
  inspector has one).

## Shape

- Backend: `player_lines.player_turn(world) -> PlayerTurn | None`, None without a player.
  ```python
  class PlayerTurn(TypedDict):
      scene_id: str | None    # the played guest's scene, if any
      state: str              # "none" | "free" | "your_turn" | "reading" | "on_stage" | "comeback"
      silence_at: float | None  # game time the turn passes in silence ("your_turn", "on_stage")
  ```
  `free` means the player is in a scene where someone else speaks next, so they can still cut in. The runtime's
  snapshot adds `player_turn`; it is computed, not saved. `types.ts` gets `PlayerTurn` and `Snapshot.player_turn`.
- `chat.ts` (pure):
  - `chatModel(snapshot) -> {members, lines, state, secondsLeft, placeholder, enabled}`. `lines` are the scene's
    turns (speaker, addressee, words; a `silence` shows as "…"). `members` are the other participants, with
    their faces and names. `secondsLeft` is `(silence_at - time) / speed`, in real seconds.
  - `nextPing(lastPingAt, now, hasText, focused) -> boolean`: a ping at most every 2 s, only while the input has
    focus and holds text.
  - `sayCommand(text, to) -> Command`: the text trimmed, `to` one of `auto`, `everyone` or a member's id.
- `chatpanel.ts` (DOM), docked along the bottom while the player has a body:
  - The scene's lines, newest last, with the player's own on the right.
  - The faces of the members; a click on a face sets "To:" to that member.
  - The "To:" picker: Auto (default), Everyone, and each member. It resets to Auto when the scene changes.
  - An input of up to 200 characters with a counter; Enter sends `say`; Shift+Enter does nothing (lines are one
    line long).
  - The states: outside a scene the input is off, with "Click someone and choose Talk"; `your_turn` shows "Your
    turn" and the seconds left; `reading` shows the sent text dimmed until it is spoken; `on_stage` changes the
    placeholder to "Speak to the hall" and hides the picker; `comeback` reads "Answer the heckler".
  - An `error` reply to `say` stays under the input until the next keystroke.

## Steps

1. Backend `player_turn`. Red first, one block on the state: `no-player` (None), `in-no-scene` (`none`),
   `someone-else-next` (`free`), `addressed` (`your_turn` with `silence_at`), `being-read` (`reading`), `on-stage`,
   `owed-a-comeback`. Check: `pytest tests/test_player_lines.py -x`.
2. `types.ts`, then `chat.ts`, red first in `frontend/tests/chat.test.ts`: `chatModel` on each state, a scene of
   three with a `silence` line, and a speed of 2; `nextPing` cases; `sayCommand` cases (trimmed, to everyone,
   to a member). Check: `npm --prefix frontend test`.
3. `chatpanel.ts` and wiring; the pings go out through `connection.send`.
4. `make check`, `make build`, then a run with a Claude key (`.env`).

## Done when

- `make check` and `make build` pass, output pasted in Results.
- With `make run` and a key, playing as Monroe: a one-to-one talk with Putin of at least six lines, then Trump
  joins and Monroe speaks to everyone, then to Trump alone. An insult starts a quarrel, and a silence makes the
  guest who spoke feel ignored. The turn waits while Monroe types. Screenshots and the scene's lines in Results.

## Results

### 2026-11-08 — built; live run still open

- `player_lines.player_turn(world)` and `PlayerTurn`, added to the snapshot as `player_turn` (computed, not saved: no schema bump).
  States: `none` (no scene, or autopilot), `free`, `your_turn` (with `silence_at`), `reading`, and, after merging S3-06,
  `on_stage` (`silence_at` is when they step down) and `comeback`.
- `chat.ts` (`chatModel`, `nextPing`, `sayCommand`) with `frontend/tests/chat.test.ts`; `chatpanel.ts` docked under the
  hall (lines, faces, To: picker, 200-char input with counter, Enter sends, pings through `connection.send`, an `error`
  reply stays under the input until the next keystroke). Faces set "To:"; it resets to Auto when the scene changes.
- `make check`: 4894 passed, mypy, `tsc`, 362 frontend tests, exit 0. `make build`: built, exit 0.
  `make golden` diff against the pre-edit baseline: empty.
- **Not done:** the `make run` look in the built-in browser and the live Monroe/Putin/Trump evening. The browser pane was
  hidden and refused navigation, and no live-model run was made. Screenshots and the scene's lines are still owed.
