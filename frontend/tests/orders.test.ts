import assert from "node:assert/strict";
import { test } from "node:test";
import { clickOrder, inspectClick, menuRows, walkAction, type Pick } from "../src/orders.ts";
import type { Action, OptionsMessage } from "../src/types.ts";

const floor: Pick = { kind: "cell", cell: [4, 5] };
const guest: Pick = { kind: "visitor", id: "putin" };
const tap: Pick = { kind: "object", id: "tap1" };
const self: Pick = { kind: "visitor", id: "monroe" };

for (const [name, pick, steering, expected] of [
  ["floor while steering walks", floor, true, { kind: "walk", cell: [4, 5] }],
  ["a guest while steering asks", guest, true, { kind: "ask", target_id: "putin" }],
  ["the tap while steering asks", tap, true, { kind: "ask", target_id: "tap1" }],
  ["the played guest asks about themself", self, true, { kind: "ask", target_id: "monroe" }],
  ["floor while watching inspects nothing", floor, false, null],
  ["a guest while watching inspects", guest, false, { kind: "inspect", id: "putin" }],
  ["the tap while watching inspects", tap, false, { kind: "inspect", id: "tap1" }],
] as const) {
  test(`clickOrder: ${name}`, () => assert.deepEqual(clickOrder(pick, steering), expected));
}

const option = (verb: string, target_id: string | null, label: string): OptionsMessage["options"][number] =>
  ({ action: { id: `${verb}:${target_id}`, verb: verb as Action["verb"], target_id }, label });
const reply = (options: OptionsMessage["options"]): OptionsMessage => ({ type: "options", target_id: null, options });
const names = { putin: "Putin", tap1: "Tap" };

for (const [name, given, expected] of [
  ["an empty reply still has Inspect", reply([]), ["Inspect"]],
  ["one option, then Inspect", reply([option("take_beer", "tap1", "Take a beer")]), ["Take a beer · Tap", "Inspect"]],
  ["several options sorted by label", reply([option("shove", "putin", "Shove"), option("chat", "putin", "Chat with a neighbor")]),
    ["Chat with a neighbor · Putin", "Shove · Putin", "Inspect"]],
  ["an unknown target shows its id", reply([option("shove", "zed", "Shove")]), ["Shove · zed", "Inspect"]],
  ["no target shows the label alone", reply([option("drink", null, "Drink")]), ["Drink", "Inspect"]],
] as const) {
  test(`menuRows: ${name}`, () => assert.deepEqual(menuRows(given, names).map((row) => row.label), expected));
}

test("menuRows: the Inspect row carries no action, the others carry theirs", () => {
  const rows = menuRows(reply([option("shove", "putin", "Shove")]), names);
  assert.equal(rows[0]?.action?.verb, "shove");
  assert.equal(rows[1]?.action, null);
});

test("walkAction: a walk_to action aimed at the cell", () => {
  const action = walkAction([4, 5]);
  assert.equal(action.verb, "walk_to");
  assert.deepEqual(action.cell, [4, 5]);
  assert.equal(action.target_id, null);
});

const members = ["putin", "trump"];
for (const [name, pick, steering, how, expected] of [
  ["inspecting a guest while steering", guest, true, { inspect: true }, { kind: "inspect", id: "putin" }],
  ["inspecting the played guest while steering", self, true, { inspect: true }, { kind: "inspect", id: "monroe" }],
  ["inspecting the floor while steering walks nowhere", floor, true, { inspect: true }, null],
  ["inspecting while watching", guest, false, { inspect: true }, { kind: "inspect", id: "putin" }],
  ["a member of the played guest's scene is replied to", guest, true, { scene: members }, { kind: "reply", to: "putin" }],
  ["a guest outside the scene is asked", { kind: "visitor", id: "bea" }, true, { scene: members }, { kind: "ask", target_id: "bea" }],
  ["the tap during a scene is asked", tap, true, { scene: members }, { kind: "ask", target_id: "tap1" }],
  ["inspecting a member of the scene", guest, true, { scene: members, inspect: true }, { kind: "inspect", id: "putin" }],
  ["a member while watching is inspected", guest, false, { scene: members }, { kind: "inspect", id: "putin" }],
  ["an empty scene replies to no one", guest, true, { scene: [] }, { kind: "ask", target_id: "putin" }],
] as const) {
  test(`clickOrder: ${name}`, () => assert.deepEqual(clickOrder(pick as Pick, steering, how), expected));
}

test("menuRows: a thing that cannot be inspected has no Inspect row", () => {
  assert.deepEqual(menuRows(reply([]), names, false), []);
  assert.deepEqual(menuRows(reply([option("take_beer", "tap1", "Take a beer")]), names, false).map((row) => row.label), ["Take a beer · Tap"]);
});

const press = (button: number, keys: Partial<Record<"shiftKey" | "altKey" | "ctrlKey" | "metaKey", boolean>> = {}) =>
  ({ button, shiftKey: false, altKey: false, ctrlKey: false, metaKey: false, ...keys });
for (const [name, event, expected] of [
  ["a plain left click acts", press(0), false],
  ["a right click inspects", press(2), true],
  ["shift-click inspects", press(0, { shiftKey: true }), true],
  ["alt-click inspects", press(0, { altKey: true }), true],
  ["ctrl-click inspects", press(0, { ctrlKey: true }), true],
  ["cmd-click inspects", press(0, { metaKey: true }), true],
  ["a middle click acts", press(1), false],
] as const) {
  test(`inspectClick: ${name}`, () => assert.equal(inspectClick(event), expected));
}
