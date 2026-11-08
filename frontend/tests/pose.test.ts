import assert from "node:assert/strict";
import { test } from "node:test";
import { isLow, onPot, poseOf, type PoseActor, type PoseWorld } from "../src/pose.ts";

const actor = (fields: Partial<PoseActor> = {}): PoseActor => ({ id: "ada", health: 100, condition: "ok", status: "idle", seat_id: null, action: null, ...fields });
const world = (actors: PoseActor[], talking: string[] = []): PoseWorld => ({ actors, conversations: talking.length ? [{ participants: talking }] : [] });
const activities = { drink: { pose: "Drinking" }, wave: { pose: "Waving" }, ponder: { pose: null } };
const doing = (verb: string, target_id: string | null = null): Partial<PoseActor> => ({ status: "interacting", action: { verb, target_id } });

for (const [name, fields, expected] of [
  ["walking", { status: "walking" }, "Walking"],
  ["on the pot", doing("use_toilet"), "Seated"],
  ["an activity pose standing", doing("drink"), "Drinking"],
  ["an activity pose seated", { ...doing("drink"), seat_id: "c1" }, "DrinkingSeated"],
  ["an activity pose with no seated form", { ...doing("wave"), seat_id: "c1" }, "Waving"],
  ["an activity without a pose, standing", doing("ponder"), "Idle"],
  ["an unknown verb, seated", { ...doing("mystery"), seat_id: "c1" }, "Seated"],
  ["seated idle", { seat_id: "c1" }, "Seated"],
  ["standing idle", {}, "Idle"],
  ["a wound beats walking", { status: "walking", health: 50 }, "Hurt"],
  ["a fighter beats an activity", { ...doing("start_fight"), seat_id: "c1" }, "Fighting"],
] as const) {
  test(`poseOf: ${name}`, () => assert.equal(poseOf(actor(fields as Partial<PoseActor>), world([]), activities), expected));
}

test("poseOf: someone giving to a visitor makes them receive", () => {
  const giver: PoseActor = actor({ id: "bob", ...doing("give", "ada") });
  assert.equal(poseOf(actor(), world([giver]), activities), "Receiving");
  assert.equal(poseOf(actor({ seat_id: "c1" }), world([giver]), activities), "ReceivingSeated");
});

test("poseOf: giving to someone else does not", () => {
  const giver: PoseActor = actor({ id: "bob", ...doing("give", "cy") });
  assert.equal(poseOf(actor(), world([giver]), activities), "Idle");
});

test("poseOf: a seated chatter talks seated; a standing one is idle", () => {
  assert.equal(poseOf(actor({ seat_id: "c1" }), world([], ["ada", "bob"]), activities), "TalkingSeated");
  assert.equal(poseOf(actor(), world([], ["ada", "bob"]), activities), "Idle");
});

test("poseOf: a wound beats receiving", () => {
  const giver: PoseActor = actor({ id: "bob", ...doing("give", "ada") });
  assert.equal(poseOf(actor({ condition: "down" }), world([giver]), activities), "KnockedOut");
});

test("poseOf: without a world there is nothing to receive or chat about", () => {
  assert.equal(poseOf(actor({ seat_id: "c1" }), null, activities), "Seated");
});

test("onPot: only an interacting visitor using the toilet", () => {
  assert.equal(onPot(actor(doing("use_toilet"))), true);
  assert.equal(onPot(actor({ status: "walking", action: { verb: "use_toilet", target_id: null } })), false);
  assert.equal(onPot(actor(doing("drink"))), false);
});

for (const [pose, expected] of [["Seated", true], ["DrinkingSeated", true], ["KnockedOut", true], ["Idle", false], ["Walking", false]] as const) {
  test(`isLow: ${pose}`, () => assert.equal(isLow(pose), expected));
}
