---
id: S3-16
title: Cut the dead air
status: done
needs: [S3-05, S3-09]
touches: [backend/tavern/evening/turn_hold.py (new), backend/tavern/evening/player_commands.py, backend/tavern/server/runtime.py, backend/tavern/server/sessions.py, frontend/src/pendingline.ts (new), frontend/src/skipahead.ts (new), frontend/src/chat.ts, frontend/src/chatpanel.ts, frontend/src/lineup.ts, frontend/src/lineupscreen.ts, frontend/src/main.ts, frontend/src/scene.ts, frontend/src/style.css, frontend/src/types.ts, frontend/src/wheelbar.ts, tests/test_turn_hold.py (new), frontend/tests/pendingline.test.ts (new), frontend/tests/skipahead.test.ts (new), frontend/tests/chat.test.ts, frontend/tests/lineup.test.ts]
---

# S3-16 — Cut the dead air (P5)

## Why

The owner's playtest found long waits in every exchange: click, walk, wait for the slot, type, wait for the
reading. The 20-second silence timer (`rules.player.silence`, S3-02/S3-05) turns the wait for the person's own
line into pressure, and the quiet stretches of an evening have no way past them. The owner decided that for a
person, auto-pause replaces the running timer.

## Scope

- In: (1) the typed line shows at once; (2) auto-pause on the played guest's due line, for a person only, with
  "let it pass"; (3) skip ahead; (4) a play-length default.
- Out: the scripted player and lockstep (they keep `rules.player.silence` exactly as before); the world coming to the
  player, the incident radar and the other later items of the analysis.

## Shape

1. **The line shows at once.** `pendingline.ts` (pure): `pendingLine` remembers the text, the scene and its turn
   count when Enter is pressed; `settle` keeps it until a turn of the player's lands after it (or, for a stage line,
   an event of theirs with those words), their scene ends or they leave it, or they let go of the wheel. The chat
   shows it at once as "… being read…", and `TavernScene.setPending` draws it as a bubble over the played guest. A
   refused `say` takes the words back into the input (as before) and now also floats a toast over the guest.
2. **Auto-pause.** `TavernRuntime(auto_pause=True)` holds the clock (`world.paused`) when the played guest owes a
   line: `evening/turn_hold.owed_line` names it (`scene:<id>:<turn>` for `your_turn`, `comeback:<heckler>:<time>`
   for a heckle owed an answer), and each line holds the clock once. Any player command but `options` (a keystroke's
   `typing`, `say`, `act`, `steer`, `let_pass`) lets it run; resume does too. Game time stands still while held, so
   the silence counts from the first keystroke, as S3-05 already counts it. The snapshot's `turn_held` says it
   holds; the chat then shows "Your turn · the hall waits" instead of a countdown, and the wheel bar "The hall
   waits for your line". New player command `let_pass`: the due line passes in silence now (`written` = the
   silence, `next_turn_at` brought to now); for a comeback it lets the heckle lapse. `TavernSessions` (a browser
   page, so a person) builds every runtime with `auto_pause=True`; lockstep, scripted, replay and golden runs never
   build a `TavernRuntime` with it. No rule or save field changed: no schema bump.
3. **Skip ahead.** `skipahead.ts` (pure): `canSkip` (wheel held, hall running, no line due), `skipFrom`,
   `skipStop`, which reads only snapshot and event fields: `player_turn.state` `your_turn`/`comeback`; a `turn` event
   after the start whose `addressee` is the played guest (`invited` when its `act` is `invite`, else
   `addressed`); a `quarrel` or `fight_started` event anywhere; `SKIP_CAP` = 180 game seconds; `over` when the
   wheel is let go or the hall was paused by hand. The wheel bar's "Skip ahead" button and the F key set speed 8
   (the server's maximum) and the old speed back at the stop, with a toast naming why. A due line stops it and
   auto-pause holds it.
4. **Play length.** Closing time is the lineup's "Evening" select: `start.minutes × 60` game seconds
   (`evening/lineup.py`), 5 minutes by default. `lineup.eveningMinutes`: with a guest picked to play and no length
   chosen, 10 minutes (`PLAY_MINUTES`, 600 game seconds); a length the person picks still wins, and "Just watch"
   keeps 5.

## Done when

- `make check` and `make build` pass, output pasted below.
- `make golden` (all five, the fifth with the scripted Monroe) and a replay of a recorded player evening are
  byte-identical before and after.
- A turn played with auto-pause and a skip ahead in the browser with the app running.

## Results

Done on `claude/p5-dead-air-107e68`, one commit per piece (line at once, auto-pause, skip ahead, play length).

- **Tests first.** `tests/test_turn_hold.py`: the clock holds when the line falls due (and runs on without
  `auto_pause`), each of keystroke / line / resume / let-it-pass lets go for good, the silence passes 20 s after the
  first keystroke however long the hold, let-it-pass speaks a silence on the next step, its refusals, `owed_line`
  over a comeback, another guest's turn and no scene, and a browser session holds. Red first (13 failing against a
  stub `owed_line` and a no-op `auto_pause`). `frontend/tests/pendingline.test.ts`, `skipahead.test.ts`, a held
  case in `chat.test.ts`, `eveningMinutes` cases in `lineup.test.ts`.
- **Golden and replay unchanged.** `make golden` into `runs/p5-golden-base` before the first backend edit and
  `runs/p5-golden-now` after, and a replay of the S3-12 live player evening (`s3-12-scripted-1/calls.jsonl`,
  guests, `monroe_night`, `monroe_meddles`, seed 1, Haiku lines) into `runs/p5-replay-base` / `-now`:

  ```
  guests-1 identical      (cmp events.jsonl and metrics.json)
  guests-5 identical
  locals-1 identical
  locals-5 identical
  monroe-5 identical
  replay identical        (cmp events.jsonl)
  ```
- **Browser** (`make run`'s two services on spare ports, Jev + Haiku live, guests cast, Monroe played with Putin and
  Trump). The Evening select showed 10 min once Monroe was picked to play; closing at 10:00. Skip ahead from 00:17
  ran at 8× to 03:08 and dropped back (the cap: Monroe stood idle, nothing concerned her). Monroe started a talk
  with Putin: the hall held at 218.2 s, "The hall waits for your line", "Let it pass", "Your turn · the hall
  waits", and stood still for 3 s. The first keystroke let it go and the countdown ran from it (`silence_at` 238.6).
  On Enter the chat showed the line "being read…" at once; Haiku read it as a joke and Putin answered. On Monroe's
  next turn the hall held again at 230.4; "Let it pass" spoke her silence and the clock ran. A line sent while
  Putin's answer was being written, then skip ahead: 8× from 233.8 until Putin's reply to Monroe at 252.3, back to
  1× at 253.3 (`addressed`). Screenshot of the held turn: `runs/p5-shots/held.jpg` (local, gitignored). The pane
  was hidden, so the Phaser canvas did not draw in screenshots and the bubble was not seen there.
- **`make check`** (pytest, mypy, `tsc`, `node:test`):

  ```
  ======================= 4952 passed in 169.81s (0:02:49) =======================
  .venv/bin/mypy
  Success: no issues found in 145 source files
  ℹ tests 407
  ℹ pass 407
  ℹ fail 0
  exit 0
  ```
- **`make build`:** `✓ built in 4.03s`, exit 0 (the usual chunk-size warning).
- **Not covered:** the pending bubble over the figure (canvas not drawn in the hidden pane); a comeback hold in the
  browser (covered by `owed_line` tests only).
