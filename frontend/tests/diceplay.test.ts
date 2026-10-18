/** The dice game's small motions: a die thrown across the table, bouncing and tumbling, then settling on a face. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { dieAt, dieFace, dieTilt, ROLL_MS, rollCycle, rollLunge } from "../src/diceplay.ts";

test("a roll starts in the air, lands, then lies still until the next throw", () => {
  assert.deepEqual(rollCycle(0, 0), { flight: 0, rest: 0 });
  assert.ok(rollCycle(ROLL_MS * 0.2, 0).flight > 0);
  assert.equal(rollCycle(ROLL_MS * 0.2, 0).rest, 0);
  const landed = rollCycle(ROLL_MS * 0.6, 0);
  assert.equal(landed.flight, -1);
  assert.ok(landed.rest > 0 && landed.rest < 1);
});

test("the two seats roll out of step, and the cycle repeats", () => {
  assert.notDeepEqual(rollCycle(100, 0), rollCycle(100, 0.5));
  assert.deepEqual(rollCycle(ROLL_MS * 2 + 300, 0.25), rollCycle(300, 0.25));
});

test("the die crosses from the player's hand to the table's middle, bouncing lower each time and still at the end", () => {
  const from = { x: 20, y: 100 };
  const to = { x: 60, y: 100 };
  assert.deepEqual(dieAt(from, to, 0), from);
  assert.deepEqual(dieAt(from, to, 1), to);
  const heights = [0.2, 0.5, 0.8].map((t: number): number => 100 - dieAt(from, to, t).y);
  assert.ok(heights.every((height: number): boolean => height >= 0));
  assert.ok(heights.some((height: number): boolean => height > 3));
  assert.ok(100 - dieAt(from, to, 0.95).y < 100 - dieAt(from, to, 0.2).y);
});

test("a die spins in the air and lies at a fixed tilt once it has landed", () => {
  assert.notEqual(dieTilt(0.2), dieTilt(0.6));
  assert.equal(dieTilt(-1), dieTilt(-1));
  assert.ok(Math.abs(dieTilt(-1)) < Math.PI / 4);
});

test("a tumbling die flickers through faces, and a landed one keeps one of the six", () => {
  const seen = new Set([0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65].map((flight: number): number => dieFace(flight, 3, 0.2)));
  assert.ok(seen.size > 2);
  for (const face of [...seen, dieFace(-1, 3, 0.2), dieFace(-1, 4, 0.2)]) assert.ok(face >= 1 && face <= 6 && Number.isInteger(face));
  assert.equal(dieFace(-1, 3, 0.2), dieFace(-1, 3, 0.2));
  assert.notEqual(dieFace(-1, 3, 0.2), dieFace(-1, 4, 0.2));
});

test("the player winds up just before the die leaves the hand and has lunged by the time it is in the air", () => {
  const toward = -1;
  const before = rollLunge(ROLL_MS * 0.9, 0, toward);
  const leaving = rollLunge(ROLL_MS * 0.02, 0, toward);
  assert.ok(before.x > 0, "leans back before the throw");
  assert.ok(leaving.x < 0, "lunges toward the table as the die leaves");
  assert.ok(Math.abs(rollLunge(ROLL_MS * 0.6, 0, toward).x) < 0.3, "sits still while the die lies");
});
