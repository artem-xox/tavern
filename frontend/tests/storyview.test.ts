import assert from "node:assert/strict";
import { test } from "node:test";
import { momentChips } from "../src/storyview.ts";
import type { Story } from "../src/types.ts";

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
