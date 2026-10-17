---
id: S2-10
title: Retelling
status: todo
needs: [S2-05]
touches: [evening/retelling.py (new), adapters/claude.py, server/runtime.py, frontend/src/]
---

# S2-10 — Retelling

## Why

The player watches a 10-minute evening and may miss the best of it. At closing, a storyteller retells the
evening as a short, funny story, and the screen shows it with the story score. This is what gets
screenshotted and shared.

## Scope

- In: a pure `evening/retelling.py` that selects the moments from the event log (S2-05's kinds first,
  then the lines around them) and builds the request; a port for the model call.
- In: a stronger model than the line writer (Claude Sonnet 5.5 or Opus 5.5): pick by cost and quality on
  three recorded evenings, record the choice in Results.
- In: every sentence cites event ids; a claim without a logged event is rejected at the boundary and the
  retelling is asked once more or shown without it.
- In: a closing screen: the title of the evening, the story in a few short chapters with the faces of who
  was involved, the moment counts, and the way back to the lineup (S2-02).
- In: `make evening` writes `retelling.md` next to `metrics.json`.
- Out: sharing outside the app.

## Shape

Model answer: `{ "title": str, "chapters": [{ "text": str, "events": [event id] }] }`, checked in
`parse_retelling`. Snapshot after closing gains `retelling`; `types.ts` with it.

## Steps

1. Test first: moment selection from a small log; `parse_retelling` rejects unknown event ids and empty
   chapters.
2. Adapter call with a fake in tests (`claude.py` pattern).
3. Headless: `retelling.md` for three recorded evenings; compare models.
4. Closing screen in the client.

## Done when

- `make check` and `make build` pass; a live evening ends on the closing screen with a cited retelling.

## Results
