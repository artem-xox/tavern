---
id: S2-02
title: Lineup screen
status: todo
needs: [S2-01]
touches: [server/api.py, server/sessions.py, frontend/src/]
---

# S2-02 — Lineup screen

## Why

The player decides who is drinking tonight. Today the browser opens straight into one fixed scenario.

## Scope

- In: a start screen with two choices: **Guests** (the famous cast) and **Locals** (the Stage 1 cast).
  Each shows its faces (the `south` view of `Idle`) and names. Choosing one starts an evening from that
  cast's scenario.
- In: a way back to the screen after closing, and from the debug panel.
- Out: picking single guests, custom cards, choosing the news (former E26). Add them later as their own
  tasks if the two-cast choice is not enough.

## Shape

- HTTP: `GET /api/casts` → `[{ "id": "guests", "title": "Guests", "faces": [character ids] }]`;
  starting a session takes `cast`. Validated at the boundary: an unknown cast is a 400.
- `types.ts` gains the cast list type.

## Steps

1. Test first: the API lists both casts and starts a session for each; an unknown cast is rejected.
2. The screen in a small module, logic kept out of Phaser and the DOM where it can be tested with `node:test`.
3. Run the app: both casts start; the debug panel can return to the screen.

## Done when

- `make check` and `make build` pass; both casts start from the browser.

## Results
