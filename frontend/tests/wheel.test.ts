import assert from "node:assert/strict";
import { test } from "node:test";
import { decisionTag, markerAt, wheelState } from "../src/wheel.ts";
import type { World } from "../src/types.ts";

/** A world with just what the wheel reads: guests present, guests expected, and the player. */
function world(player: World["player"], present: string[], expected: string[] = []): World {
  const guest = (id: string) => ({ id, name: id.toUpperCase(), sprite: `${id}-art` });
  return { player, paused: false, actors: present.map(guest), departed: [], expected: expected.map(guest) } as unknown as World;
}

test("wheelState: no player, no bar", () => {
  assert.equal(wheelState(world(null, ["monroe"])), null);
});

test("wheelState: a guest on the floor, steered", () => {
  assert.deepEqual(wheelState(world({ actor_id: "monroe", steering: true }, ["monroe", "putin"])),
    { face: "monroe-art", name: "MONROE", steering: true, paused: false, present: true });
});

test("wheelState: autopilot and a paused evening", () => {
  const paused = { ...world({ actor_id: "monroe", steering: false }, ["monroe"]), paused: true };
  const state = wheelState(paused);
  assert.deepEqual([state?.steering, state?.paused], [false, true]);
});

test("wheelState: a played guest who has not come in yet is shown as not present", () => {
  const state = wheelState(world({ actor_id: "monroe", steering: true }, [], ["monroe"]));
  assert.deepEqual([state?.name, state?.present], ["MONROE", false]);
});

test("wheelState: a played guest the world does not know is not drawn", () => {
  assert.equal(wheelState(world({ actor_id: "ghost", steering: true }, ["monroe"])), null);
});

test("markerAt: above the head, the same for steering and autopilot, bobbing with the time", () => {
  const still = markerAt(100, 200, 0);
  assert.equal(still.x, 100);
  assert.ok(still.y < 200 - 60, "above the name");
  assert.notEqual(markerAt(100, 200, 300).y, still.y);
  assert.deepEqual(markerAt(100, 200, 0), still);
});

test("decisionTag: the player's own decisions are named, a guest's follow their source", () => {
  assert.equal(decisionTag("jev", true), "PLAYER");
  assert.equal(decisionTag("jev", false), "JEV");
  assert.equal(decisionTag("local", false), "LOCAL");
  assert.equal(decisionTag(undefined, false), "LOCAL");
});
