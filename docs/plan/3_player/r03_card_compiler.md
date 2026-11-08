---
id: S3-R03
title: Retire the card compiler, which no client calls
status: done
needs: [S3-R00]
touches: [mind/card_compiler.py, server/cards_api.py, server/api.py, app.py, scripts/evening.py, .env.example, tests/test_card_compiler.py, tests/test_cards_api.py, docs/CHARACTER_CATALOG.md]
---

# S3-R03 — Retire the card compiler

## Why

`POST /api/cards/compile` turns a player's written card into params with Haiku. Nothing calls it: the
browser client only fetches `/api/characters`, `/api/casts` and the `/ws` socket (`frontend/src/main.ts`,
`connection.ts`), and custom cards were dropped with E26 ("custom cards are out of scope", TECH_DEBT.md).
It keeps 133 lines of code, 177 lines of tests and an `ask` port in `create_app` alive for no one. If
Stage 3 ever lets the player write their own character, it comes back from git history
(`backend/tavern/mind/card_compiler.py` at the commit before this task).

## Scope

- In: deleting the compiler, its HTTP route, its tests and the wiring that exists only for them.
- Out: `cards.parse_card_text`: `cards.parse_card` uses it and `tests/test_cards.py` specifies it; it stays.
  The `"card"` kind used as a label in `tests/test_recording_claude.py`: test data for the recorder, stays.

## Approval

Deletes two test files, `tests/test_card_compiler.py` (88 lines) and `tests/test_cards_api.py` (89 lines),
because the behavior they specify is removed. **Approved by the owner, 2026-11-07.**

## Steps

1. Delete `backend/tavern/mind/card_compiler.py`, `backend/tavern/server/cards_api.py`,
   `tests/test_card_compiler.py`, `tests/test_cards_api.py`, one commit.
2. `backend/tavern/server/api.py`: drop the `card_routes` import (line 22), the
   `app.include_router(card_routes(ask))` call (line 161), the `ask` parameter of `create_app` and its
   docstring entry (lines 75, 103–104). `grep -n "ask" backend/tavern/server/*.py` must then find nothing
   that refers to the compiler.
3. `backend/tavern/app.py`: stop passing `ask=ask` to `create_app` (line 76). `ask` itself stays: it feeds the
   line writer, the intender and the stage writer. Reword the two comments that mention the compiler
   (the docstring of `create_default_app`, about line 35, and `_claude_port`, about line 83): Haiku writes
   lines, intentions and stage numbers.
4. `scripts/evening.py`: drop `"card": HAIKU_5_5` from `TARIFFS` (line 58); no evening records a `card` call.
5. `.env.example`: the line "Claude Haiku 5.5 compiles player-written character cards; ..." becomes "Claude Haiku
   5.5 writes lines, intentions and stage numbers; empty runs the labeled scripted writer."
6. `docs/CHARACTER_CATALOG.md` about line 228 mentions "the existing card compiler": reword the item so it no
   longer points at it.
7. `grep -rniE "card.compiler|cards/compile|compile_card|offline_card|RejectedParams|CompiledCard" --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=.git .`
   finds only `docs/plan/*/archive.md` (history) and this task file.

Steps 2–6 are one commit. Golden check after each commit: empty diff (the compiler is never on an evening's
path).

## Done when

- `make check` passes; the golden check prints nothing. Both pasted into Results.
- The grep of step 7 is clean.

## Results

Two commits on `claude/s3-r03-cards-f132c6`: step 1 (deletions), steps 2-6 (wiring, tariff, `.env.example`, catalog).

- `make check`: `4681 passed in 355.95s`; frontend `tests 318, pass 318, fail 0`; exit 0. (4706 before: the two deleted files held 25 cases.)
- Golden: `make golden GOLDEN=runs/golden-now && diff -r runs/golden-base runs/golden-now` printed nothing, after the last commit.
- Step 7 grep (excluding `runs/`): only `docs/plan/*/archive.md`, this file, and mentions in files this lane may not edit: `docs/plan/README.md:61`, `docs/plan/3_player/README.md:26,52`, `docs/plan/3_player/r02_private_names.md:22` (all describe the task, not code). The integrator keeps those.
