/** The dart game's small motions: the thrower's lunge, the dart's flight, the sparks of a hit and the winner's cheer. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { CHEER_SECONDS, cheerSparks, dartAt, hitSparks, throwCycle, throwMotion, THROW_MS } from "../src/dartplay.ts";

test("a throw starts in the air and ends in the board, then the hit fades before the next throw", () => {
  assert.deepEqual(throwCycle(0, 0), { flight: 0, hit: 0 });
  assert.ok(throwCycle(THROW_MS * 0.2, 0).flight > 0);
  assert.equal(throwCycle(THROW_MS * 0.2, 0).hit, 0);
  const landed = throwCycle(THROW_MS * 0.42, 0);
  assert.equal(landed.flight, -1);
  assert.ok(landed.hit > 0.9);
  assert.ok(throwCycle(THROW_MS * 0.95, 0).hit < landed.hit);
});

test("the cycle repeats and a phase moves it, so two players never throw as one", () => {
  assert.deepEqual(throwCycle(THROW_MS * 3 + 100, 0), throwCycle(100, 0));
  assert.notDeepEqual(throwCycle(100, 0), throwCycle(100, 0.5));
});

test("the dart flies from the hand to the board in an arc that is highest midway", () => {
  const from = { x: 80, y: 100 };
  const to = { x: 40, y: 100 };
  assert.deepEqual(dartAt(from, to, 0), from);
  assert.deepEqual(dartAt(from, to, 1), to);
  assert.ok(dartAt(from, to, 0.5).y < 100);
  assert.equal(dartAt(from, to, 0.5).x, 60);
});

test("the thrower leans back to wind up, then lunges toward the board and settles", () => {
  const windUp = throwMotion(THROW_MS * 0.1, 0, -1);
  const release = throwMotion(THROW_MS * 0.3, 0, -1);
  assert.ok(windUp.x > 0, "winds up away from the board");
  assert.ok(release.x < 0, "lunges toward the board");
  assert.ok(Math.abs(throwMotion(THROW_MS * 0.9, 0, -1).x) < 0.3);
  assert.equal(throwMotion(THROW_MS * 0.1, 0, 1).x, -windUp.x);
});

test("a hit throws sparks outward that fade, and none are left once the burst is over", () => {
  const [fresh, spent] = [hitSparks(0.95)[0]!, hitSparks(0.75)[0]!];
  assert.equal(hitSparks(0.95).length, 6);
  assert.ok(Math.hypot(spent.x, spent.y) > Math.hypot(fresh.x, fresh.y));
  assert.ok(spent.alpha < fresh.alpha);
  assert.deepEqual(hitSparks(0.3), []);
  assert.deepEqual(hitSparks(0), []);
});

test("the winner's cheer sparkles for a few seconds and then stops", () => {
  assert.ok(cheerSparks(0.5, 1000).length > 0);
  assert.deepEqual(cheerSparks(CHEER_SECONDS, 1000), []);
  assert.deepEqual(cheerSparks(-1, 1000), []);
});
