---
id: S2-15
title: A stage worth climbing
status: done
needs: [S2-14]
touches: [data/tavern.json, frontend/src/furniture.ts, frontend/src/stage.ts, frontend/src/scene.ts]
---

# S2-15 — A stage worth climbing

## Why

The stage is one plank tile by the right wall (`furniture.drawStage`): from above it reads as a crate, and nothing
about it changes while someone speaks from it. After this task it is a platform the room faces, and a number on it is
visible across the hall before anyone reads a word.

## Scope

- In: a 3-by-2 platform along the right wall (three cells long, two deep) with a step, a lectern and two candle
  footlights; the speaker raised while anywhere on it; the footlights flare while a number is on.
- Out: PixelLab art (ask first: it spends credits); a crowd that walks over to the stage; sound.

## Shape

- `data/tavern.json`: the stage object moves from (17, 9), 1×1, to `x` 17, `y` 7, `width` 2, `height` 3,
  `interaction_spots` `[[17, 8]]` (the front edge's middle), `walkable` true, `facing` west. Those cells are empty
  floor today. Saved worlds keep their old 1×1 stage, which the client still draws.
- `stage.stageLift(actor, target)`: the lift applies anywhere inside the target stage's cells, not only its anchor.
- `furniture.drawStage(g, object, size)`: draws any width and height: boards, a front edge with a step, a lectern by
  the speaker's spot, a candle at each front corner.
- `scene.ts`: the footlights glow brighter while someone stands on the stage doing `give_speech`.
- No snapshot change.

## Tests that change, because the behaviour they pin is what this task replaces

- `test_speeches.py::test_the_hall_has_a_stage_with_one_speaker_spot_on_the_stage_itself` checks the spot is the
  stage's anchor cell; it becomes "the one spot is a cell of the stage". `STAGE_SPOT` moves to (17, 8).

## Steps

1. The stage object and the spot — check: `pytest tests/test_speeches.py`.
2. Lift anywhere on the stage — check: `npm --prefix frontend test` (`frontend/tests/stage.test.ts`).
3. Drawing and the footlights — check: `make build`, and a look in the browser during a live evening.

## Done when

- `make check` and `make build` pass.
- A screenshot of a number on the new stage.

## Results

Built: the 2-by-3 stage in `data/tavern.json` (cells 17-18 by 7-9, the spot at (17, 8)), `stage.ts` (`stageLift`
over the whole stage, `footlights`, `performing`), `furniture.drawStage` (boards, a front trim and a step, a lectern,
bunting, brass dishes) and `drawFootlights` (a flame on each dish that flares, with a warm glow, during a number).
`make check` and `make build` pass. In the browser (live Guests evening, 177 s): Trump up on the new stage roasting
Greta, her heckle over her head across the hall, his comeback over his; the footlights glow around him
(`runs/stage-heckle.jpg`, `runs/stage-comeback.jpg`, not committed). A wall candle already hung at (19, 9), beside the
stage's back edge.

