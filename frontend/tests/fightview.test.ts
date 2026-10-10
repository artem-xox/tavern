import assert from "node:assert/strict";
import { test } from "node:test";
import { blowFlash, blowShake, cudgelHand, fightMotion, fightPose, healthTint, lastBlowOn, limp, showsCudgel, starsOrbit, type Body } from "../src/fightview.ts";

const body = (fields: Partial<Body> = {}): Body => ({ health: 100, condition: "ok", status: "idle", seat_id: null, action: null, ...fields });

test("fightPose: a whole guest looks as they usually do", () => {
  assert.equal(fightPose(body()), null);
});

for (const [name, fields, expected] of [
  ["a fighter is in their stance", { action: { verb: "start_fight" }, status: "interacting" }, "Fighting"],
  ["one waiting a turn squares up", { action: { verb: "join_fight" }, status: "interacting" }, "Fighting"],
  ["one knocked out lies", { condition: "out", health: 9 }, "KnockedOut"],
  ["one thrown down lies", { condition: "down" }, "KnockedOut"],
  ["one reeling stands bent", { condition: "staggered" }, "Hurt"],
  ["one groggy stands bent", { condition: "groggy", health: 55 }, "Hurt"],
  ["one groggy in a chair slumps", { condition: "groggy", health: 55, seat_id: "w" }, "HurtSeated"],
  ["one hurt walks bent", { health: 50, status: "walking", seat_id: null }, "Hurt"],
  ["one hurt in a chair slumps", { health: 50, seat_id: "w" }, "HurtSeated"],
  ["one just bruised enough is not yet hurt", { health: 70 }, null],
] as const) {
  test(`fightPose: ${name}`, () => assert.equal(fightPose(body(fields as Partial<Body>)), expected));
}

test("fightPose: a fighter who has been knocked down lies, not fights", () => {
  assert.equal(fightPose(body({ condition: "out", action: { verb: "recover" } })), "KnockedOut");
});

test("healthTint: none while whole, deeper as they are beaten", () => {
  assert.deepEqual([100, 70, 69, 40, 39, 5].map(healthTint), [0xffffff, 0xffffff, 0xffd2c8, 0xffd2c8, 0xff9f94, 0xff9f94]);
});

test("fightMotion: the two lunge out of step, toward whom they face", () => {
  const first = fightMotion(100, "east", 0);
  const second = fightMotion(100, "west", 1);
  assert.ok(first.x > 2, "a swing east moves east");
  assert.ok(second.x < 1, "the other has not swung");
});

test("fightMotion: a lunge south moves down the screen and north up", () => {
  assert.ok(fightMotion(100, "south", 0).y > 2);
  assert.ok(fightMotion(100, "north", 0).y < -2);
});

test("fightMotion: between lunges they only circle", () => {
  const still = fightMotion(700, "east", 0);
  assert.ok(Math.abs(still.x) < 2 && Math.abs(still.y) < 1.5);
});

test("blowShake and blowFlash: strongest at once, gone after half a second", () => {
  assert.equal(blowFlash(0), 1);
  assert.equal(blowFlash(0.5), 0);
  assert.equal(blowFlash(-1), 0);
  assert.deepEqual(blowShake(0.6, 1000), { x: 0, y: 0, angle: 0 });
  assert.ok(Math.abs(blowShake(0.05, 1000).angle) > 0);
});

test("limp: a bob upward that never sinks below the feet", () => {
  for (const ms of [0, 100, 400, 777, 1500]) assert.ok(limp(ms) <= 0 && limp(ms) >= -3);
});

test("starsOrbit: three stars, a third of a turn apart", () => {
  const stars = starsOrbit(0);
  assert.equal(stars.length, 3);
  assert.ok(Math.abs(stars[0]!.x - 14) < 1e-9);
});

test("cudgelHand: held on the side the guest faces, higher and tilted more in a stance", () => {
  for (const facing of ["north", "south", "east", "west"] as const) {
    const hand = cudgelHand(facing, false);
    const raised = cudgelHand(facing, true);
    assert.ok(raised.y < hand.y);
    assert.ok(Math.abs(raised.angle) > Math.abs(hand.angle));
  }
  assert.equal(cudgelHand("north", false).behind, true);
  assert.equal(cudgelHand("south", false).behind, false);
});

test("showsCudgel: not on one lying down or asleep", () => {
  assert.deepEqual(["Idle", "Walking", "Fighting", "Hurt", "KnockedOut", "SleepingSeated"].map(showsCudgel),
    [true, true, true, true, false, false]);
});

test("lastBlowOn: the latest swing that landed on them, never their own", () => {
  const fights = [
    { a: "ada", b: "bea", exchanges: [
      { time: 1, attacker: "ada", hit: true }, { time: 1, attacker: "bea", hit: false },
      { time: 2, attacker: "ada", hit: false }, { time: 2, attacker: "bea", hit: true }] },
    { a: "cid", b: "dan", exchanges: [{ time: 9, attacker: "cid", hit: true }] },
  ];
  assert.equal(lastBlowOn(fights, "bea"), 1);
  assert.equal(lastBlowOn(fights, "ada"), 2);
  assert.equal(lastBlowOn(fights, "dan"), 9);
  assert.equal(lastBlowOn(fights, "cid"), null);
  assert.equal(lastBlowOn(fights, "eve"), null);
  assert.equal(lastBlowOn([], "ada"), null);
});
