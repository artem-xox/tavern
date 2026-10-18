import assert from "node:assert/strict";
import { test } from "node:test";

import { STAGE_LIFT, stageLift } from "../src/stage.ts";

const stage = { kind: "stage", x: 17, y: 9 };

const cases: { id: string; actor: { x: number; y: number }; target: { kind: string; x: number; y: number } | undefined; lift: number }[] = [
  { id: "on the stage", actor: { x: 17, y: 9 }, target: stage, lift: STAGE_LIFT },
  { id: "walking up to it", actor: { x: 16, y: 9 }, target: stage, lift: 0 },
  { id: "no target", actor: { x: 17, y: 9 }, target: undefined, lift: 0 },
  { id: "another kind of target on the same cell", actor: { x: 17, y: 9 }, target: { kind: "chair", x: 17, y: 9 }, lift: 0 },
];
for (const { id, actor, target, lift } of cases) test(`stageLift: ${id}`, () => assert.equal(stageLift(actor, target), lift));
