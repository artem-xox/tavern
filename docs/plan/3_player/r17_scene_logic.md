---
id: S3-R17
title: Take pose choice and click picking out of the Phaser scene into pure, tested modules
status: todo
needs: []
touches: [frontend/src/scene.ts, frontend/src/pose.ts (new), frontend/src/picking.ts (new), frontend/tests/pose.test.ts (new), frontend/tests/picking.test.ts (new)]
---

# S3-R17 — Pure pose and picking

## Why

The player's first input is a click: on the floor to walk, on a guest to talk, on a table to sit. Today the
only click logic is inside `TavernScene` (`frontend/src/scene.ts`, 397 lines, at the 400 limit), where no test
reaches it. AGENTS.md: "`frontend/` keeps logic out of Phaser and the DOM. A pure module is tested in
`frontend/tests/<module>.test.ts`." Two pieces of logic in the scene are pure already in all but location:

- **Pose choice**: `onPot` and `actorPose` (about lines 302–317) and the tables `SEATED_POSES`, `LOW_POSES`
  they use. They read an actor, the world, and the activities table; they return a pose name.
- **Picking**: `click` and `hover` (about lines 355–388) turn a pointer position into a cell, the visitor
  under it (within 0.65 of a tile of their drawn position), or the object whose footprint covers the cell, and
  `hover` words what is under the pointer.

## Scope

- In: `frontend/src/pose.ts` with `poseOf(actor, world, activities): string` and `isLow(pose): boolean` (if
  `LOW_POSES` is read outside `actorPose`); `frontend/src/picking.ts` with `cellAt(x, y, map)`,
  `visitorAt(x, y, positions, tileSize)`, `objectAt(cell, objects)` and `hoverText(...)`; the scene calls
  them. Both modules import no Phaser and touch no DOM. Moved logic stays exactly as it is, including the
  `0.65` reach and the hover wording.
- Out: drawing, interpolation, any new input. The editing mode's cell toggle stays in the scene, calling
  `cellAt`.

## Shape

`visitorAt` takes `positions: ReadonlyMap<string, { x: number; y: number }>` (the drawn container positions),
so it needs no Phaser object. `hoverText` takes what it needs as plain data (the world, the cell, the visitor
under the pointer with their emote word, the editing flag) and returns the string the scene shows today.

## Steps

1. `pose.ts` and `frontend/tests/pose.test.ts`, test first: walking → `Walking`; on the pot → `Seated`; given
   something → `Receiving` (seated → `ReceivingSeated`); an activity pose standing and seated; seated
   chatting → `TalkingSeated`; seated idle → `Seated`; standing idle → `Idle`; a wound pose wins over all
   (`fightPose`). Then the scene calls it. One commit. — check: `npm --prefix frontend test`,
   `npm --prefix frontend run check`.
2. `picking.ts` and `frontend/tests/picking.test.ts`, test first: a pointer outside the map → null cell; a
   pointer within reach of a visitor → that visitor, the nearest when two are close; an object's footprint
   with width and height; hover text for a tap (stock), a seat with an owner, an empty cell, the editing
   hint. Then the scene calls them. One commit. Same checks.
3. Run the app (`make run`), click a guest (the inspector opens), hover the tap and a chair (the hover line
   reads as before), toggle a wall in the debug editor. Note it in Results.

## Done when

- `make check` and `make build` pass. Pasted into Results.
- `scene.ts` is about 340 lines; `grep -n "Math.hypot\|Math.floor(pointer" frontend/src/scene.ts` finds nothing.

## Results

Filled in when the task is done.
