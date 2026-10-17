---
id: S2-01
title: Two casts
status: todo
needs: []
touches: [characters/, adapters/characters.py, mind/characters.py, data/scenarios/, scripts/evening.py, .agents/skills/add-npc, docs/CHARACTER_CATALOG.md]
---

# S2-01 — Two casts

## Why

Famous guests and the Stage 1 locals should not share one flat `characters/` list or one scenario. We
want to run an evening of either, and to add a guest without touching the locals' tests.

## Scope

- In: `characters/locals/<id>/`, `characters/guests/<id>/`, `characters/staff/hob/`. The catalog loader
  reads all three; the folder is the cast. A character id stays unique across casts.
- In: one scenario per cast: `data/scenarios/locals.json` (today's `first_evening.json`) and
  `data/scenarios/guests.json` (empty guest list until S2-04). `make evening CAST=locals|guests`.
- Out: the lineup screen (S2-02). New card fields (S2-03).

## Shape

- Catalog entry gains `cast: "locals" | "guests" | "staff"`, taken from the folder, never written in
  `character.json`. Check that `role: bartender` lives only in `staff/`.
- Browser character data gains `cast`; `types.ts` changes with it.
- Saves: art paths are resolved from the id, so no schema bump is expected. If a save embeds a path, ask
  the user before bumping.

## Steps

1. `git mv` the six locals and Hob; the catalog tests still pass with the new folders.
   Check: `.venv/bin/python -m pytest tests/ -k catalog -x`.
2. Test first: a character in two casts, or a bartender outside `staff/`, is a `ValueError` naming it.
3. Scenarios per cast and the `CAST` option in `scripts/evening.py` and `make evening`.
4. Update `add-npc` and [CHARACTER_CATALOG.md](../../CHARACTER_CATALOG.md) for the new layout.

## Done when

- `make check` and `make build` pass; `make evening CAST=locals SEED=5` replays the same `events.jsonl` as
  before the move.

## Results
