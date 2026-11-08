---
id: S3-R10
title: What a line writer sees moves to mind/; the written line's type leaves the import cycle
status: done
needs: [S3-R02]
touches: [social/turns.py, social/scenes.py, mind/turn_view.py (new), mind/scripted.py, mind/haiku_turns.py, mind/cards.py, social/stage_lines.py, adapters/tracing.py, evening/mind_loop.py, tests]
---

# S3-R10 — The turn view

## Why

When the player joins a scene, their client needs the scene from the speaker's side, and the guests' writer
must see the player's lines. Both rest on `social/turns.py` `turn_view`, which today sits among the timing of
turns (claim, deliver, speak). Three problems:

1. **The type of a written line crosses an import cycle** (D16): `TurnResult` is defined in `social/turns.py`,
   but `social/scenes.py:26` and `mind/scripted.py:12` need it and are imported by `turns`, so both import it
   under `if TYPE_CHECKING:`.
2. **A view in the wrong package.** AGENTS.md: `mind/` is "what a guest observes and decides". `turn_view` and
   its helpers (`_participants`, `_add_invitations`, `_mind`, `_grudges`, `_just_fought`, `_aims_at`, about
   lines 122–241) build the writer's view of a guest; they are why `social/turns.py` imports
   `mind.briefing`, `mind.cards`, `mind.feelings` and `mind.portrait`.
3. **A copy.** The card words of a speaker are built twice, identically:
   `{**{key: card[key] for key in TEXT_FIELDS}, **persona_words(card)}` in `social/turns.py:200` and
   `social/stage_lines.py:112`.

## Scope

- In: `TurnResult` moves to `social/scenes.py`, beside `Turn`; `turn_view` and its helpers move verbatim to a
  new `backend/tavern/mind/turn_view.py` ("What a line writer sees of a scene: the speaker, the company, the
  invitations and acts on offer"); a `card_words(card)` function in `mind/cards.py` replaces the two copies.
- Out: `TurnWriter`, `reading_time`, `next_speaker`, `cutting_in`, `check_turn`, `claim_turns`,
  `deliver_turn`, `speak_turns`: the timing and the boundary stay in `social/turns.py`. The view's content:
  every key and value stays the same.

## Approval

Test edits, import lines only, **approved by the owner, 2026-11-07**: the 16 test files that import `turn_view` from
`tavern.social.turns` import it from `tavern.mind.turn_view` (`grep -lw turn_view tests/*.py`).

## Steps

1. Move `TurnResult` to `scenes.py`; update `turns.py`, `mind/haiku_turns.py`, `mind/scripted.py`,
   `adapters/tracing.py`, `evening/mind_loop.py`; delete the two `TYPE_CHECKING` blocks. One commit.
   — check: `grep -rn "TYPE_CHECKING" backend` lists only `hall/state.py`; `.venv/bin/mypy`; `make test`.
2. `card_words` in `mind/cards.py`, red/green in `tests/test_cards.py` (a card without persona, one with);
   the two copies call it. One commit. Golden empty diff.
3. Move `turn_view` and helpers to `mind/turn_view.py`; `claim_turns` imports it; the approved import edits.
   One commit. — check: `make test`, golden empty diff, `wc -l backend/tavern/social/turns.py` (about 280).
4. In `docs/plan/TECH_DEBT.md`, row D16: strike the `scripted.py` and `scenes.py` parts; only `state.py`
   remains. Same commit as step 1.

## Done when

- `make check` passes; golden check prints nothing. Pasted into Results.
- `social/turns.py` imports nothing from `mind/` except `mind.scripted` (the fallback writer) and
  `mind.turn_view`.

## Results

Done 2026-11-07, three commits (step 4, the D16 row, is in the step 1 commit).

- `TurnResult` is in `social/scenes.py`; `grep -rn TYPE_CHECKING backend` lists only `hall/state.py`.
- `card_words` in `mind/cards.py`, red/green in `tests/test_cards.py`; both copies call it.
- `turn_view` and its helpers are in `mind/turn_view.py`. `social/turns.py` imports from `mind/` only
  `mind.scripted` and `mind.turn_view`. The 16 test files changed their import line only.
- **Deviation:** `next_speaker` and `_cutting_in` (with `CUT_IN_AFTER`) moved to `mind/turn_view.py` too. The view
  reads them, and `turns.py` imports the view, so leaving them in `turns.py` would recreate the import cycle this
  task removes. Two more import lines changed for it: `evening/mind_loop.py` and `tests/test_turns.py`
  (`next_speaker`). `social/turns.py` is 199 lines, not about 280, for the same reason.

```
make check: 4651 passed in 295.71s; mypy: Success: no issues found in 133 source files; frontend 318 pass, 0 fail
golden: make golden GOLDEN=runs/golden-now && diff -r runs/golden-base runs/golden-now  -> prints nothing
```
