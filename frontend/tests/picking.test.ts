import assert from "node:assert/strict";
import { test } from "node:test";
import { cellAt, hoverText, objectAt, visitorAt, type PickObject } from "../src/picking.ts";

const map = { width: 10, height: 8, tile_size: 32 };
const object = (fields: Partial<PickObject> = {}): PickObject => ({ id: "o1", kind: "chair", name: "Chair", x: 2, y: 3, reserved_by: null, stock: null, ...fields });

for (const [name, x, y, expected] of [
  ["inside the map", 70, 40, [2, 1]],
  ["the first cell", 0, 0, [0, 0]],
  ["the last cell", 319, 255, [9, 7]],
  ["left of the map", -1, 10, null],
  ["above the map", 10, -5, null],
  ["right of the map", 320, 10, null],
  ["below the map", 10, 256, null],
] as const) {
  test(`cellAt: ${name}`, () => assert.deepEqual(cellAt(x, y, map), expected));
}

const positions = new Map([["ada", { x: 100, y: 100 }], ["bob", { x: 110, y: 100 }]]);
for (const [name, x, y, expected] of [
  ["on a visitor", 100, 100, "ada"],
  ["the nearest of two close ones", 108, 100, "bob"],
  ["within reach", 100, 120, "ada"],
  ["out of reach", 100, 140, null],
] as const) {
  test(`visitorAt: ${name}`, () => assert.equal(visitorAt(x, y, positions, 32), expected));
}
test("visitorAt: nobody drawn", () => assert.equal(visitorAt(5, 5, new Map(), 32), null));

const wide = object({ id: "table", x: 4, y: 2, width: 3, height: 2 });
for (const [name, cell, expected] of [
  ["a one-cell object", [2, 3], "o1"],
  ["inside a wide footprint", [6, 3], "table"],
  ["just past a footprint", [7, 2], null],
  ["an empty cell", [0, 0], null],
] as const) {
  test(`objectAt: ${name}`, () => assert.equal(objectAt([...cell] as [number, number], [object(), wide])?.id ?? null, expected));
}
test("objectAt: no objects", () => assert.equal(objectAt([1, 1], []), null));

const view = (fields: Partial<Parameters<typeof hoverText>[0]> = {}): Parameters<typeof hoverText>[0] =>
  ({ cell: [2, 3], object: null, owner: null, playerNames: [], emoted: null, editing: false, ...fields });
for (const [name, fields, expected] of [
  ["an emoting visitor", { emoted: { name: "Ada", word: "laughing" } }, "Ada · laughing"],
  ["a tap shows stock", { object: object({ kind: "tap", name: "Tap", stock: 5 }) }, "Tap · available · 5 left · cell 2, 3"],
  ["an empty tap", { object: object({ kind: "tap", name: "Tap", stock: null }) }, "Tap · available · 0 left · cell 2, 3"],
  ["a seat with an owner", { object: object({ reserved_by: "ada" }), owner: "Ada" }, "Chair · reserved · Ada's seat · cell 2, 3"],
  ["a game table names the players", { object: object({ kind: "dice_table", name: "Dice", game: { players: [] } as never }), playerNames: ["Ada", "Bob"] }, "Dice · available · Ada and Bob playing · cell 2, 3"],
  ["an object with appeal and comforts", { object: object({ appeal: 0.5, comforts: ["soft", "warm"] }) }, "Chair · available · appeal 0.50 (soft, warm) · cell 2, 3"],
  ["an empty cell", {}, "Click a visitor to inspect · cell 2, 3"],
  ["the editing hint", { editing: true }, "Click to toggle obstacle · cell 2, 3"],
] as const) {
  test(`hoverText: ${name}`, () => assert.equal(hoverText(view(fields as Partial<Parameters<typeof hoverText>[0]>)), expected));
}
