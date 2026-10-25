import assert from "node:assert/strict";
import { test } from "node:test";
import { canStart, DEFAULT_MINUTES, MAX_GUESTS, startCommand, togglePick } from "../src/lineup.ts";

test("togglePick: a face clicked once is picked, clicked again is put back", () => {
  assert.deepEqual(togglePick([], "edda"), ["edda"]);
  assert.deepEqual(togglePick(["edda", "rurik"], "edda"), ["rurik"]);
});

test("togglePick: picks keep the order they were clicked in", () => {
  assert.deepEqual(togglePick(togglePick([], "saye"), "edda"), ["saye", "edda"]);
});

test("togglePick: a ninth face is not picked, but a picked one can still be removed", () => {
  const full: string[] = ["a", "b", "c", "d", "e", "f", "g", "h"];
  assert.equal(MAX_GUESTS, 8);
  assert.deepEqual(togglePick(full, "i"), full);
  assert.deepEqual(togglePick(full, "h"), ["a", "b", "c", "d", "e", "f", "g"]);
});

test("canStart: from one to eight guests", () => {
  assert.equal(canStart([]), false);
  assert.equal(canStart(["a"]), true);
  assert.equal(canStart(["a", "b", "c", "d", "e", "f", "g", "h"]), true);
  assert.equal(canStart(["a", "b", "c", "d", "e", "f", "g", "h", "i"]), false);
});

test("startCommand: the chosen cast, guests and minutes, five minutes by default", () => {
  assert.equal(DEFAULT_MINUTES, 5);
  assert.deepEqual(startCommand("guests", ["trump"]), { type: "start", cast: "guests", guests: ["trump"], minutes: 5 });
  assert.deepEqual(startCommand("locals", ["edda", "rurik"], 10), { type: "start", cast: "locals", guests: ["edda", "rurik"], minutes: 10 });
});
