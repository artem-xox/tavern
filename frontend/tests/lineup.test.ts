import assert from "node:assert/strict";
import { test } from "node:test";
import { canStart, DEFAULT_MINUTES, keepPlayer, MAX_GUESTS, startCommand, togglePick } from "../src/lineup.ts";

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
  assert.deepEqual(startCommand("guests", ["trump"]), { type: "start", cast: "guests", guests: ["trump"], minutes: 5, player: null });
  assert.deepEqual(startCommand("locals", ["edda", "rurik"], 10), { type: "start", cast: "locals", guests: ["edda", "rurik"], minutes: 10, player: null });
});

test("startCommand: the played guest is sent with the start", () => {
  assert.deepEqual(startCommand("guests", ["monroe", "putin"], 5, "monroe"), { type: "start", cast: "guests", guests: ["monroe", "putin"], minutes: 5, player: "monroe" });
});

test("startCommand: the player must be one of the picked guests", () => {
  assert.throws(() => startCommand("guests", ["putin"], 5, "monroe"), /monroe/);
});

test("keepPlayer: the choice stands while the guest is picked and resets to just watching when their face is put back", () => {
  assert.equal(keepPlayer(["monroe", "putin"], "monroe"), "monroe");
  assert.equal(keepPlayer(togglePick(["monroe", "putin"], "monroe"), "monroe"), null);
  assert.equal(keepPlayer([], null), null);
});
