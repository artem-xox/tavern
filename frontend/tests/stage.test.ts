import assert from "node:assert/strict";
import { test } from "node:test";

import { STAGE_LIFT, footlights, performing, stageLift } from "../src/stage.ts";

const stage = { kind: "stage", x: 17, y: 9 };

const cases: { id: string; actor: { x: number; y: number }; target: { kind: string; x: number; y: number } | undefined; lift: number }[] = [
  { id: "on the stage", actor: { x: 17, y: 9 }, target: stage, lift: STAGE_LIFT },
  { id: "walking up to it", actor: { x: 16, y: 9 }, target: stage, lift: 0 },
  { id: "no target", actor: { x: 17, y: 9 }, target: undefined, lift: 0 },
  { id: "another kind of target on the same cell", actor: { x: 17, y: 9 }, target: { kind: "chair", x: 17, y: 9 }, lift: 0 },
];
for (const { id, actor, target, lift } of cases) test(`stageLift: ${id}`, () => assert.equal(stageLift(actor, target), lift));


const platform = { kind: "stage", x: 17, y: 7, width: 2, height: 3, facing: "west" as const };

const onPlatform: { id: string; actor: { x: number; y: number }; lift: number }[] = [
  { id: "at the speaker's spot", actor: { x: 17, y: 8 }, lift: STAGE_LIFT },
  { id: "at the back corner", actor: { x: 18, y: 9 }, lift: STAGE_LIFT },
  { id: "just in front of it", actor: { x: 16, y: 8 }, lift: 0 },
  { id: "just beyond its end", actor: { x: 17, y: 10 }, lift: 0 },
];
for (const { id, actor, lift } of onPlatform) test(`stageLift on a 2-by-3 stage: ${id}`, () => assert.equal(stageLift(actor, platform), lift));

test("footlights: one at each front corner of a stage facing west", () => {
  assert.deepEqual(footlights(platform, 32), [{ x: 17 * 32 + 5, y: 7 * 32 + 5 }, { x: 17 * 32 + 5, y: 10 * 32 - 5 }]);
});

const speaking = { x: 17, y: 8, status: "interacting", action: { verb: "give_speech" } };
const shows: { id: string; actors: { x: number; y: number; status: string; action: { verb: string } | null }[]; on: boolean }[] = [
  { id: "a performer up there", actors: [speaking], on: true },
  { id: "still walking up", actors: [{ ...speaking, status: "walking" }], on: false },
  { id: "someone only crossing it", actors: [{ ...speaking, action: { verb: "take_beer" } }], on: false },
  { id: "an empty hall", actors: [], on: false },
];
for (const { id, actors, on } of shows) test(`performing: ${id}`, () => assert.equal(performing(actors, platform), on));
