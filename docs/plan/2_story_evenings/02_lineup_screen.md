---
id: S2-02
title: Lineup screen
status: done
needs: [S2-01]
touches: [server/api.py, server/sessions.py, frontend/src/]
---

# S2-02 — Lineup screen

## Why

The player decides who is drinking tonight. Today the browser opens straight into one fixed scenario.

## Scope

- In: a start screen. Step one: **Guests** (the famous cast) or **Locals** (the Stage 1 cast). Step two: the
  cast's faces (the `south` view of `Idle`, the name and the card's `occupation`) to click, from 1 to 8
  picked; the evening's length (3, 5, 10, 15 or 30 minutes at the standard speed, 5 by default).
- In: a way back to the screen after closing (the recap window) and from the controls ("Change guests").
- Out: custom cards, choosing the news (former E26).

## Shape

- HTTP: `GET /api/casts` → `[{ "id", "title", "characters": [{ "id", "name", "description" }] }]`, 404 without
  `scenarios_dir`.
- WebSocket command `{ "type": "start", "cast", "guests": [ids], "minutes" }` opens a running evening. The
  cast's scenario is the template: `evening/lineup.py` swaps in the picked guests (all due at opening, the
  opening window staggers them), `closes_at = minutes × 60`, last call at 90 %, and cuts the news to what
  the picked guests know (no ailment when nobody picked can fall ill). A later `reset` replays the lineup.
  Refused with a `ValueError`: an unknown cast, fewer than 1 or more than 8 guests, a repeat, a character of
  another cast, minutes outside 1–60.
- `types.ts`: `Cast`, `CastMember` and the `start` command.

## Steps

1. Test first: the API lists both casts and starts a session for each; an unknown cast is rejected.
2. The screen in a small module, logic kept out of Phaser and the DOM where it can be tested with `node:test`.
3. Run the app: both casts start; the debug panel can return to the screen.

## Done when

- `make check` and `make build` pass; both casts start from the browser.

## Results

Done. Start screen: cast, then 1–6 faces, then the length (5 min default); `start` command and `GET /api/casts`. Guests enter 15 s apart (squeezed into half of a short evening) so they do not crowd the bar at once. `make check`: 3613 passed; `make build` ok.
