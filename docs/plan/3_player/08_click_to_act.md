---
id: S3-08
title: Click to act
status: todo
needs: [S3-03, S3-07]
touches: [frontend/src/orders.ts (new), frontend/src/ordermenu.ts (new), frontend/src/picking.ts, frontend/src/scene.ts, frontend/src/connection.ts, frontend/src/main.ts, frontend/src/style.css, frontend/src/types.ts, frontend/tests/orders.test.ts (new)]
---

# S3-08 — Click to act

## Why

S3-03 gives the backend `act`, `options` and `walk_to`, and nobody can send them yet. The owner chose clicks:
a click on the floor walks there, and a click on a thing or a person opens a menu of the verbs open right now,
which is the same list a guest's mind chooses from. After this task the player can play their body from the
browser: walk, pour a beer, sit, drink, play darts or dice, climb the stage, give, shove, start a talk.

## Scope

- In: the click rule while steering, the menu, the destination mark, and errors shown as short toasts.
- Out: typing (S3-09); keyboard movement (the owner chose clicks); clicks while watching or on autopilot, which
  keep selecting for the inspector as today.

## Shape

- `orders.ts` (pure):
  - `clickOrder(pick, steering) -> {kind: "walk", cell} | {kind: "ask", target_id} | {kind: "inspect", id} | null`.
    While steering: a free floor cell gives `walk`, and a person or an object gives `ask`. While not steering,
    every pick gives `inspect`, as `picking.ts` does today.
  - `menuRows(reply, names) -> {label, action}[]`. Each row reads as the label plus the target's name ("Chat with
    a neighbor · Putin", "Take a beer · Tap"). Rows are sorted by label, and the menu ends with an "Inspect" row.
- `ordermenu.ts` (DOM): it opens at the click point when the `options` reply for that target arrives; a row sends
  `act`; Esc, a click elsewhere, or a new click closes it. An empty reply shows "Nothing to do here now".
- `connection.ts` hands `options` and `error` messages to their handlers; today it reads snapshots only. An
  `error` while steering shows as a toast above the played guest for 3 s.
- The destination mark: a small mark on the cell a `walk_to` goes to, until the guest arrives or does something
  else (from the snapshot's action).

## Steps

1. `orders.ts` red first in `frontend/tests/orders.test.ts`: `clickOrder` cases (floor while steering, a guest
   while steering, the tap while steering, any pick while watching, a pick of the played guest themself, which
   gives `ask` with the verbs aimed at oneself) and `menuRows` cases (empty reply, one option, several
   options sorted, a target unknown to `names`). Check: `npm --prefix frontend test`.
2. `connection.ts`: `options` and `error` messages, with a test if the routing is pure.
3. `ordermenu.ts`, the toast and the destination mark; then wire them in `main.ts` and `scene.ts`.
4. `make check`, `make build`, then a run.

## Done when

- `make check` and `make build` pass, output pasted in Results.
- With `make run`, playing as Monroe: walk across the hall, take a beer at the tap, sit at a table, drink, climb
  the stage, shove Trump, and open a talk with Putin (the scene starts; S3-09 adds the words). Screenshots of the
  menu and of one refusal toast in Results.

## Results
