/** Which way a fireplace opens, and where its own coordinates land on the map, for a fireplace in each wall. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { frameOf, hearthFacing } from "../src/hearth.ts";
import type { WorldObject } from "../src/types.ts";

const SIZE = 32;
const MAP_WIDTH = 20;

function fireplace(x: number, y: number, width: number, height: number): WorldObject {
  return { id: "fireplace", kind: "fireplace", name: "Fireplace", x, y, width, height, interaction_spots: [], stock: null, reserved_by: null };
}

const walls: { id: string; hearth: WorldObject; facing: [number, number]; origin: [number, number]; far: [number, number]; mouth: [number, number] }[] = [
  { id: "in the north wall, opening south", hearth: fireplace(9, 0, 3, 1), facing: [0, 1], origin: [288, 0], far: [384, 32], mouth: [336, 32] },
  { id: "in the south wall, opening north", hearth: fireplace(9, 13, 3, 1), facing: [0, -1], origin: [384, 448], far: [288, 416], mouth: [336, 416] },
  { id: "in the west wall, opening east", hearth: fireplace(0, 5, 1, 3), facing: [1, 0], origin: [0, 160], far: [32, 256], mouth: [32, 208] },
  { id: "in the east wall, opening west", hearth: fireplace(19, 5, 1, 3), facing: [-1, 0], origin: [640, 256], far: [608, 160], mouth: [608, 208] },
];

for (const { id, hearth, facing, origin, far, mouth } of walls) {
  test(`hearthFacing: ${id}`, () => assert.deepEqual(hearthFacing(hearth, MAP_WIDTH), facing));
  test(`frameOf: ${id}, the wall's back corner, the room's far corner, and the middle of the mouth`, () => {
    const frame = frameOf(hearth, SIZE, MAP_WIDTH);
    assert.deepEqual([frame.at(0, 0).x, frame.at(0, 0).y], origin);
    assert.deepEqual([frame.at(frame.length, frame.depth).x, frame.at(frame.length, frame.depth).y], far);
    assert.deepEqual([frame.at(frame.length / 2, frame.depth).x, frame.at(frame.length / 2, frame.depth).y], mouth);
  });
}
