/** The dice table's resting dice leave the picture while a game is on, and come back when it ends. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { diceInPlay, mapParts } from "../src/mapview.ts";
import type { HallMap } from "../src/mapview.ts";

type Obj = HallMap["objects"][number];

function table(game: Obj["game"]): Obj {
  return { id: "dice-table", kind: "dice_table", name: "Dice table", x: 10, y: 8, interaction_spots: [], stock: null, reserved_by: null, game };
}

function hall(game: Obj["game"]): HallMap {
  return { width: 20, height: 14, tile_size: 32, blocked: [], objects: [table(game)] };
}

const waiting = { players: ["edda"], since: 4, ends_at: null };
const playing = { players: ["edda", "rurik"], since: 4, ends_at: 29 };

test("diceInPlay: only a game with two seated and an end is in play", () => {
  assert.deepEqual([null, undefined, waiting, playing].map((game) => diceInPlay(table(game))), [false, false, false, true]);
});

test("a game starting in earnest redraws the furniture, so the resting dice go", () => {
  assert.notEqual(mapParts(hall(null)).furniture, mapParts(hall(playing)).furniture);
});

test("a lone player waiting does not redraw the furniture", () => {
  assert.equal(mapParts(hall(null)).furniture, mapParts(hall(waiting)).furniture);
});

test("a game's end redraws the furniture, so the resting dice come back", () => {
  assert.notEqual(mapParts(hall(playing)).furniture, mapParts(hall(null)).furniture);
});
