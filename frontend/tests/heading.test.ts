import assert from "node:assert/strict";
import { test } from "node:test";
import { headingOf, headingToObject } from "../src/heading.ts";

// The same cases as `test_facing_toward_a_cell` in tests/test_expression.py: the server and the client turn alike.
for (const [name, dx, dy, expected] of [
  ["east", 3, 1, "east"],
  ["west", -3, 1, "west"],
  ["south is down the screen", 0, 3, "south"],
  ["north", 0, -3, "north"],
  ["a corner to the south-east", 2, 2, "south-east"],
  ["a corner to the north-west", -2, -2, "north-west"],
  ["a corner to the north-east", 2, -2, "north-east"],
  ["a corner to the south-west", -2, 2, "south-west"],
  ["two across, one down", 2, 1, "south-east"],
  ["one across, three down", 1, 3, "south"],
  ["no distance", 0, 0, null],
] as const) {
  test(`headingOf: ${name}`, () => {
    assert.equal(headingOf(dx, dy), expected);
  });
}

const table = { x: 4, y: 3, width: 2, height: 1 };

for (const [name, from, expected] of [
  ["straight above a wide table's left cell", { x: 4, y: 2 }, "south"],
  ["straight above its right cell", { x: 5, y: 2 }, "south"],
  ["beside its end", { x: 3, y: 3 }, "east"],
  ["beside its far end", { x: 6, y: 3 }, "west"],
  ["at a corner of it", { x: 3, y: 2 }, "south-east"],
  ["at its far corner", { x: 6, y: 4 }, "north-west"],
  ["standing on it", { x: 4, y: 3 }, null],
] as const) {
  test(`headingToObject: ${name}`, () => {
    assert.equal(headingToObject(from, table), expected);
  });
}

test("headingToObject: an object with no size is one cell", () => {
  assert.equal(headingToObject({ x: 1, y: 1 }, { x: 2, y: 2 }), "south-east");
});
