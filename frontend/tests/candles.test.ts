/** Where the hall's wall candles hang, which way they shine, and how their light compares with the fire's. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { CANDLES, candleLight, glowRadius, GLOW_RINGS } from "../src/candles.ts";
import { flicker, HEARTH_GLOW_RADIUS } from "../src/hearth.ts";

const SIZE = 32;
const room = JSON.parse(readFileSync(new URL("../../data/tavern.json", import.meta.url), "utf8")) as {
  width: number;
  blocked: [number, number][];
  objects: { x: number; y: number; width?: number; height?: number; walkable?: boolean }[];
};

const walls = new Set(room.blocked.map(([x, y]: [number, number]): string => `${x},${y}`));
const furniture = new Set(room.objects.filter((item) => !item.walkable).flatMap((item) => {
  const cells: string[] = [];
  for (let dy = 0; dy < (item.height ?? 1); dy += 1) for (let dx = 0; dx < (item.width ?? 1); dx += 1) cells.push(`${item.x + dx},${item.y + dy}`);
  return cells;
}));

test("there are four candles: the privy, the front door and two more on the walls", () => {
  assert.equal(CANDLES.length, 4);
});

for (const candle of CANDLES) {
  const where = `(${candle.x}, ${candle.y})`;
  test(`the candle at ${where} hangs on a wall cell and shines into free floor`, () => {
    assert.ok(walls.has(`${candle.x},${candle.y}`), "not on a blocked wall cell");
    const { dx, dy } = candleLight(candle, room.width, SIZE);
    const front = `${candle.x + dx},${candle.y + dy}`;
    assert.ok(!walls.has(front) && !furniture.has(front), `${front} is not free floor`);
  });
}

const sides: { id: string; candle: { x: number; y: number }; shines: [number, number]; at: [number, number] }[] = [
  { id: "east wall, shining west", candle: { x: 19, y: 2 }, shines: [-1, 0], at: [608, 80] },
  { id: "south wall, shining north", candle: { x: 11, y: 13 }, shines: [0, -1], at: [368, 416] },
  { id: "west wall, shining east", candle: { x: 0, y: 9 }, shines: [1, 0], at: [32, 304] },
  { id: "north wall, shining south", candle: { x: 5, y: 0 }, shines: [0, 1], at: [176, 32] },
];

for (const { id, candle, shines, at } of sides) {
  test(`candleLight: ${id}, on the wall's room-side edge`, () => {
    const light = candleLight(candle, 20, SIZE);
    assert.deepEqual([light.dx, light.dy, light.x, light.y], [...shines, ...at]);
  });
}

test("a candle's glow reaches less than the hearth's", () => {
  assert.ok(glowRadius(SIZE, GLOW_RINGS) < HEARTH_GLOW_RADIUS * SIZE);
});

test("two candles flicker out of step at the same moment", () => {
  assert.notEqual(flicker(1000, 0), flicker(1000, 2.1));
});

test("the fire's flicker, with no phase, is the one it has always had", () => {
  const time = 1234;
  assert.equal(flicker(time), 0.82 + 0.1 * Math.sin(time / 170) + 0.08 * Math.sin(time / 53));
});
