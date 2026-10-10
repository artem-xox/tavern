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

test("stills: every character ships a sleeping pose in four views", () => {
  const sleeping = stills().filter((item) => item.key.includes("-SleepingSeated-"));
  assert.equal(sleeping.length % 4, 0);
  assert.ok(sleeping.length >= 24);
});

test("stills: every guest loads the six combat poses in four views", () => {
  const poses = ["Fighting", "KnockedOut", "Hurt", "HurtSeated", "Shoving", "HelpingUp"];
  const combat = stills().filter((item) => poses.some((pose) => item.key.includes(`-${pose}-`)));
  assert.equal(combat.length, 6 * poses.length * 4);
});
