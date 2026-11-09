import assert from "node:assert/strict";
import { test } from "node:test";
import { momentChips } from "../src/storyview.ts";
import type { Story } from "../src/story.ts";

const story = (moments: Record<string, number>): Story => ({ moments, score: 0 });

test("momentChips: an evening with no moments shows no chips", () => {
  assert.deepEqual(momentChips(story({ quarrel: 0, fight: 0 })), []);
});

test("momentChips: only the moments that happened, with their emoji and count, biggest first", () => {
  assert.deepEqual(
    momentChips(story({ fell_asleep: 1, quarrel: 3, fight: 0, gift: 1 })),
    ["😡 quarrel ×3", "💤 fell asleep ×1", "🎁 gift ×1"],
  );
});

test("momentChips: a kind the client does not know still shows, with a plain mark", () => {
  assert.deepEqual(momentChips(story({ stampede: 2 })), ["✨ stampede ×2"]);
});

import { retellingWindow } from "../src/storyview.ts";

const told = { title: "T", chapters: [{ text: "S", events: [0], actors: ["ada"] }] };

for (const [name, telling, recap, dismissed, expected] of [
  ["nothing is being told: no window", false, null, false, "hidden"],
  ["the storyteller is working: ask to wait", true, null, false, "waiting"],
  ["the recap is ready: show it", false, told, false, "told"],
  ["the recap is ready and was closed: stay closed", false, told, true, "hidden"],
  ["waiting cannot be closed away", true, null, true, "waiting"],
] as const) {
  test(`retellingWindow: ${name}`, () => {
    assert.equal(retellingWindow(telling, recap, dismissed), expected);
  });
}

import { playerChapters, playerFirst } from "../src/storyview.ts";
import type { CitedEvent } from "../src/story.ts";

const cite = (type: string, actor_id: string, player = false): CitedEvent => ({ type, actor_id, player });
const chapter = (...events: number[]) => ({ text: "S", events, actors: [] });
const log: Record<number, CitedEvent> = {
  0: cite("turn", "ada", true), 1: cite("player_act", "ada"), 2: cite("turn", "ada"), 3: cite("quarrel", "bram"), 4: cite("player_act", "bram"),
};

for (const [name, chapters, playerId, expected] of [
  ["no player: nothing is marked", [chapter(0), chapter(1)], null, []],
  ["no chapter cites the player", [chapter(2), chapter(3)], "ada", []],
  ["a typed line and an act mark their chapters", [chapter(2), chapter(0, 3), chapter(1), chapter(3)], "ada", [1, 2]],
  ["a cited position missing from the log is ignored", [chapter(99), chapter(99, 1)], "ada", [1]],
  ["an act of someone else's is not the player's", [chapter(4)], "ada", []],
] as const) {
  test(`playerChapters: ${name}`, () => {
    assert.deepEqual(playerChapters({ title: "T", chapters: [...chapters] }, log, playerId), expected);
  });
}

for (const [name, ids, playerId, expected] of [
  ["no player leaves the order", ["bram", "ada"], null, ["bram", "ada"]],
  ["the player moves to the front", ["bram", "ada", "cy"], "ada", ["ada", "bram", "cy"]],
  ["a player who is not in the chapter adds no face", ["bram"], "ada", ["bram"]],
  ["no faces", [], "ada", []],
] as const) {
  test(`playerFirst: ${name}`, () => {
    assert.deepEqual(playerFirst(ids, playerId), expected);
  });
}
