---
id: S3-11
title: The player in the story
status: todo
needs: [S3-04]
touches: [backend/tavern/evening/retelling.py, backend/tavern/server/runtime.py, frontend/src/storyview.ts, frontend/src/main.ts, frontend/src/types.ts, frontend/tests/storyview.test.ts]
---

# S3-11 — The player in the story

## Why

At closing a strong model retells the evening from its log (S2-10). With a player, the most interesting
question for the person reading is "what did *I* do to this evening?", and right now neither the storyteller
nor the closing screen knows who was played. The stage's "done when" asks for a retelling that shows a player
line changing the main incident, so the retelling must cite the player's lines like any other.

## Scope

- In: a note to the storyteller naming the played guest; the closing screen marks the played guest and the
  chapters that cite the player's own lines or actions.
- Out: telling the story in the second person, since the owner keeps it shareable: third person, the
  character's name; counting player moments differently in the story score, since a moment counts the same
  whoever caused it (S3-12 may revisit `ignored`).

## Shape

- `retelling_question(events, score, note)` already takes a `note`. With a player, the runtime passes "The
  player played <name>. Tell the evening as usual, in the third person; their lines and acts are events like
  any other." Without a player, the note is as today. The note is used in the question; its wording is not
  pinned by a test.
- The events shown to the storyteller (`told`) keep the `player` field of `turn` events (S3-04) and the
  `player_act` events (S3-03), so a chapter can cite them.
- Snapshot: `retelling` stays as it is. The client knows the played guest from `state.player` (S3-02).
- `storyview.ts` (pure): `playerChapters(retelling, events, playerId) -> number[]` lists the chapters that cite an
  event of the player's (a `turn` with `player: true`, or a `player_act`). The closing screen marks those
  chapters, puts the played guest's face first among the faces with a "You" label, and leaves the rest as it is.

## Steps

1. The note. Red first: with a player, the question's content holds the played guest's name; without one, the
   question equals today's (a test comparing against `retelling_question(events, score)` with no note).
   Check: `pytest tests/test_retelling.py -x`.
2. `told` keeps the `player` field and `player_act` events: a case in the same test file.
3. `storyview.ts`: `playerChapters` red first in `frontend/tests/storyview.test.ts` (no player, no cited player
   event, two chapters citing the player's line and act, a cited event index outside the log). Then the screen.
4. `make check`, `make build`, then a live run of `make evening PLAYER=data/players/monroe_meddles.json` if S3-10
   is merged, or a played evening in the browser if it is not.

## Done when

- `make check` and `make build` pass, output pasted in Results.
- Results paste one chapter of a live retelling that cites a player's line, and a screenshot of the closing
  screen with the "You" face and the marked chapter.

## Results
