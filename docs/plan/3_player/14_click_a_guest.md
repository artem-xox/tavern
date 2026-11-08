---
id: S3-14
title: Click a guest
status: done
needs: [S3-08, S3-09]
touches: [frontend/src/orders.ts, frontend/src/dialogue.ts (new), frontend/src/chatpanel.ts, frontend/src/scene.ts, frontend/src/main.ts, frontend/src/style.css, frontend/tests/orders.test.ts, frontend/tests/dialogue.test.ts (new)]
---

# S3-14 — Click a guest

## Why

The owner's playtest found two problems with clicking a guest while playing. First, while steering, a click on a guest
asked for `options`, and an empty reply gave no menu at all, so another guest's stats and mind could not be looked at.
Second, the S3-09 chat sat docked under the hall, out of sight, and the player had to find it and click into it before
typing.

## Scope

- In: what a click on a guest does while playing; the dialogue popup and when it opens and closes.
- Out: backend changes. `say`, `typing` and the addressee stay as S3-04, S3-05 and S3-09 built them, and the snapshot
  already has everything the popup needs (`player_turn`, the scene's turns, `player.steering`).

## Shape

- Inspecting is always possible. A right click, or a click with Shift, Alt, Ctrl or Cmd held (`inspectClick`), inspects
  the guest under it, played or not, steering or not. The order menu always ends with "Inspect" for a guest, even when
  there is nothing to do with them now; objects, which the inspector does not show, get no Inspect row. The inspector
  shows the other guest as an observer sees them, as it did before.
- `clickOrder(pick, steering, {inspect, scene})`: while steering, a click on another member of the played guest's scene
  is `reply`; any other guest or thing is `ask` (the menu), the floor is `walk`.
- The dialogue popup (`chatpanel.ts`), centred over the screen, with the input focused when it opens:
  - shows who the scene is with (or "On the stage", "A heckler"), its last six lines, the "To:" choices (Auto,
    Everyone, a face per member), "Your turn · N s" with "they wait while you type" while the S3-05 pings hold the
    turn, and a "More with X…" button that opens the order menu for the addressed guest.
  - `dialogueStep` (`dialogue.ts`, pure) decides when it is open and to whom it speaks. It opens by itself when a
    scene with the played guest starts (or the player takes the wheel mid-scene), and when the scene's turn, a
    heckler's comeback or the stage comes to the player, at "To: auto" unless it was already open. Esc, the × and a
    sent line close it; it stays closed until a new scene or a new turn. A refused line reopens it with the text.
    The scene ending or autopilot closes it.
  - Closed in a scene, a small chip at the bottom ("In a scene · click a guest to answer", or the turn's seconds)
    reopens it.
- A click on a guest in the same scene goes straight into the popup, addressed to them, rather than through a "Reply"
  row in the menu. That is the flow the owner described (someone answers, click them, answer), and it costs one click
  instead of two. The other verbs on that guest stay one click away under "More with X…", and a modifier or right
  click still inspects them.

## Results

### 2026-11-08 — built and played

- `orders.ts`: `clickOrder(pick, steering, {inspect, scene})` (adds `reply`), `inspectClick`, and `menuRows` with
  Inspect always (an object gets none). `dialogue.ts`: `dialogueStep`. `chatpanel.ts` is now the centred popup;
  `scene.ts` turns off the canvas context menu and passes the inspect flag; `main.ts` wires reply and "More with X…".
- Tests first (`frontend/tests/orders.test.ts`, new `dialogue.test.ts`): red with 28 behavioural failures, then green.
  One existing case changed, as the task asked: `menuRows: an empty reply has no rows` is now
  `an empty reply still has Inspect`, expecting `["Inspect"]`.
- `make check`: 4936 passed (pytest), mypy "Success: no issues found in 144 source files", `tsc`, 401 frontend tests,
  exit 0. `make build`: built, exit 0.
- Played in the built-in browser (backend on 8010 with the `.env` key, so Jev and Haiku were live), as Monroe with
  Putin and Trump. The pane was hidden, which stops `requestAnimationFrame` and so Phaser; for the run only, a scratch
  Vite plugin outside the repo swapped it for a 16 ms timer.
  - Right click on Putin while steering Monroe: the inspector showed Putin (mind, intention, goal "talk to Marilyn
    Monroe"). A left click opened the menu "Walk over for a word · Vladimir Putin", "Inspect".
  - "Walk over for a word": the scene started and the popup opened by itself in the middle, "Talking with Vladimir
    Putin · Your turn · 15 s", the field focused. Typed at once: "Mr Putin, you look like a man who never buys the
    first round." Enter sent it and closed the popup.
  - Putin answered "Mrs Monroe, you wound me. I buy the round when the table is worth it. Dice? Loser pays."; the
    turn came back and the popup reopened with both lines. Esc closed it and left the "Your turn · 14 s" chip at the
    bottom; a click on Putin reopened it addressed to him, with "More with Vladimir Putin…".
  - Replied "Dice it is, darling. But if I win, you sing.": read as accepting the dice, the scene ended, the popup
    closed, and both went to the dice table.
- Not checked: the stage and comeback headings in the browser (covered by `dialogueStep` cases only).
