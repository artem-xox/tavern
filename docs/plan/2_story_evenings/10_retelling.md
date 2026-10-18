---
id: S2-10
title: Retelling
status: doing
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
`parse_retelling`. Snapshot after closing gains `retelling` and `telling` (the storyteller is writing); `types.ts` with it.

Frozen when built: an event's id is its position in the evening's log, and the question lists lines as
`[#12 01:05] words`. A chapter cited only lines it was shown. The server adds `actors` (IDs, in the order
first cited) to each chapter, so the client shows the faces without trusting the model for who did what.

## Steps

1. Test first: moment selection from a small log; `parse_retelling` rejects unknown event ids and empty
   chapters.
2. Adapter call with a fake in tests (`claude.py` pattern).
3. Headless: `retelling.md` for three recorded evenings; compare models.
4. Closing screen in the client.

## Done when

- `make check` and `make build` pass; a live evening ends on the closing screen with a cited retelling.

## Results

Built (the first version, the recap, came with S2-05 and is replaced by this one):

- `evening/retelling.py`: `told` picks the lines (moments first, then the talk within three events of each,
  then the rest of the colour thinned evenly, at most 60); `retelling_question` numbers them;
  `parse_retelling` rejects a missing title, no or too many chapters, empty or long text, a chapter that cites
  nothing, and a citation that is not an integer or was never shown. `retell` asks once; a rejected answer is
  asked again with the reason; then only the chapters whose citations stand are kept, and if none does, nothing is shown.
- Live: the runtime starts the telling when the last guest leaves; the snapshot has `telling` and `retelling`.
  A failure is said in the event log and the score stays.
- Closing window in the client: "Please wait" while `telling`, then the title, the chapters each with the
  portraits of who is in it, the moment counts, and Close / Change guests (back to the lineup) / New evening.
  Seen working in a real browser with a fake storyteller; the barkeep stays in the hall, so the window follows the
  server, not the roster.
- `make evening` writes `retelling.md` (each chapter with the events it was told from) when `ANTHROPIC_API_KEY`
  is in `.env`; a replay asks nobody.

Not done, because both need an `ANTHROPIC_API_KEY` the building session did not have:

- Choosing the model by cost and quality on three recorded evenings: the call is wired to Claude Sonnet 5.5
  (`scripts/evening.py` `RETELLING_MODEL`, `app.py`), not yet compared with Opus 5.5.
- A live evening ending on the closing window with a real cited retelling.
