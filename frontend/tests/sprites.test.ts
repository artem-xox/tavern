import assert from "node:assert/strict";
import { test } from "node:test";
import { shippedPose, stills, type SpriteSheet } from "../src/sprites.ts";

const sheet = (poses: readonly string[]): SpriteSheet => ({ size: 68, lift: -16, poses });

test("shippedPose: a shipped pose is drawn as asked", () => {
  assert.equal(shippedPose(sheet(["Idle", "Seated", "SleepingSeated"]), "SleepingSeated"), "SleepingSeated");
});

test("shippedPose: a missing seated pose falls back to Seated, so a sleeper stays in their chair", () => {
  assert.equal(shippedPose(sheet(["Idle", "Seated"]), "SleepingSeated"), "Seated");
});

test("shippedPose: a missing standing pose falls back to Idle", () => {
  assert.equal(shippedPose(sheet(["Idle", "Seated"]), "Darts"), "Idle");
});

test("shippedPose: a missing seated pose of a sprite without Seated falls back to Idle", () => {
  assert.equal(shippedPose(sheet(["Idle"]), "DrinkingSeated"), "Idle");
});

test("stills: every character ships a sleeping pose in eight views", () => {
  const sleeping = stills().filter((item) => item.key.includes("-SleepingSeated-"));
  assert.equal(sleeping.length % 8, 0);
  assert.ok(sleeping.length >= 48);
});

test("shippedPose: a fight pose a sprite lacks stands in for by what it has", () => {
  assert.equal(shippedPose(sheet(["Idle", "Talking"]), "Fighting"), "Talking");
  assert.equal(shippedPose(sheet(["Idle", "Seated", "SleepingSeated"]), "KnockedOut"), "SleepingSeated");
  assert.equal(shippedPose(sheet(["Idle"]), "Hurt"), "Idle");
  assert.equal(shippedPose(sheet(["Idle", "Seated"]), "HurtSeated"), "Seated");
  assert.equal(shippedPose(sheet(["Idle", "Giving"]), "Shoving"), "Giving");
});

test("shippedPose: the fight poses are used when a sprite ships them", () => {
  assert.equal(shippedPose(sheet(["Idle", "Talking", "Fighting"]), "Fighting"), "Fighting");
});

test("stills: every guest loads the six combat poses in eight views", () => {
  const poses = ["Fighting", "KnockedOut", "Hurt", "HurtSeated", "Shoving", "HelpingUp"];
  const combat = stills().filter((item) => poses.some((pose) => item.key.includes(`-${pose}-`)));
  assert.equal(combat.length, 6 * poses.length * 8);
});
