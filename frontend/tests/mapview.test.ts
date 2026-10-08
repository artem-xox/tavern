/** What of the map's picture a change in the map redraws: the canvas size, the floor, or the furniture. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { mapParts } from "../src/mapview.ts";
import type { HallMap } from "../src/mapview.ts";

type Obj = HallMap["objects"][number];

function object(fields: Partial<Obj> & { id: string; kind: Obj["kind"] }): Obj {
  return { name: fields.id, x: 1, y: 1, interaction_spots: [], stock: null, reserved_by: null, ...fields };
}

function room(changes: Partial<HallMap> = {}): HallMap {
  return {
    width: 20, height: 14, tile_size: 32, blocked: [[0, 0], [1, 0]],
    objects: [object({ id: "tap", kind: "tap", stock: 20 }), object({ id: "table-1", kind: "table", x: 5, y: 5, width: 2, height: 1 }), object({ id: "chair-1", kind: "chair", x: 4, y: 5, facing: "east" })],
    ...changes,
  };
}

function withObject(map: HallMap, id: string, fields: Partial<Obj>): HallMap {
  return { ...map, objects: map.objects.map((item: Obj): Obj => item.id === id ? { ...item, ...fields } : item) };
}

type Redrawn = { size: boolean; floor: boolean; furniture: boolean };

const changes: { id: string; next: HallMap; redrawn: Redrawn }[] = [
  { id: "the same map again", next: room(), redrawn: { size: false, floor: false, furniture: false } },
  { id: "the tap's stock going down", next: withObject(room(), "tap", { stock: 19 }), redrawn: { size: false, floor: false, furniture: false } },
  { id: "a queue forming at the tap", next: withObject(room(), "tap", { queue: [{ actor_id: "edda", since: 3 }] }), redrawn: { size: false, floor: false, furniture: false } },
  { id: "a dice game starting", next: withObject(room(), "table-1", { game: { players: ["edda", "rurik"], since: 4, ends_at: null } }), redrawn: { size: false, floor: false, furniture: false } },
  { id: "a chair being reserved", next: withObject(room(), "chair-1", { reserved_by: "edda" }), redrawn: { size: false, floor: false, furniture: true } },
  { id: "a chair turning", next: withObject(room(), "chair-1", { facing: "west" }), redrawn: { size: false, floor: false, furniture: true } },
  { id: "an obstacle being added", next: room({ blocked: [[0, 0], [1, 0], [2, 0]] }), redrawn: { size: false, floor: true, furniture: false } },
  { id: "a table moving", next: withObject(room(), "table-1", { x: 6 }), redrawn: { size: false, floor: true, furniture: true } },
  { id: "a wider hall", next: room({ width: 21 }), redrawn: { size: true, floor: true, furniture: false } },
  { id: "bigger tiles", next: room({ tile_size: 48 }), redrawn: { size: true, floor: true, furniture: true } },
];

for (const { id, next, redrawn } of changes) {
  test(`mapParts: ${id}`, () => {
    const before = mapParts(room());
    const after = mapParts(next);
    assert.deepEqual({ size: before.size !== after.size, floor: before.floor !== after.floor, furniture: before.furniture !== after.furniture }, redrawn);
  });
}

test("mapParts: an empty hall has parts too", () => {
  const empty = mapParts(room({ blocked: [], objects: [] }));
  assert.equal(typeof empty.size, "string");
  assert.equal(typeof empty.floor, "string");
  assert.equal(typeof empty.furniture, "string");
});
