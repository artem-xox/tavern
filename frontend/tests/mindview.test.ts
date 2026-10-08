/** What the inspector makes of a visitor's inner state: pips for needs, merged thoughts, opinion bars. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { mergeThoughts, needPips, needTone, needWord, opinionBar } from "../src/mindview.ts";
import type { Thought } from "../src/types.ts";

function thought(text: string, mood: number, expiresAt: number = 100): Thought {
  return { kind: "chat", about: null, text, mood, opinion: 0, expires_at: expiresAt, source_event: "e" };
}

const pips: { id: string; urgency: number; pips: number }[] = [
  { id: "no urge at all is a full bar", urgency: 0, pips: 5 },
  { id: "a faint urge is still full", urgency: 4, pips: 5 },
  { id: "a tenth rounds up", urgency: 10, pips: 5 },
  { id: "a fifth is four", urgency: 20, pips: 4 },
  { id: "half is three", urgency: 50, pips: 3 },
  { id: "two thirds is two", urgency: 66, pips: 2 },
  { id: "a strong urge is one", urgency: 86, pips: 1 },
  { id: "the worst is none", urgency: 100, pips: 0 },
  { id: "above 100 is held at none", urgency: 120, pips: 0 },
  { id: "below 0 is held at full", urgency: -5, pips: 5 },
];
for (const { id, urgency, pips: expected } of pips) test(`needPips: ${id}`, () => assert.equal(needPips(urgency), expected));

test("needPips: a number that is not one is refused", () => assert.throws(() => needPips(Number.NaN), /urgency/));

const levels: { pips: number; word: string; tone: string }[] = [
  { pips: 0, word: "desperate", tone: "bad" }, { pips: 1, word: "very low", tone: "bad" }, { pips: 2, word: "low", tone: "warn" },
  { pips: 3, word: "fine", tone: "good" }, { pips: 4, word: "good", tone: "good" }, { pips: 5, word: "full", tone: "good" },
];
for (const { pips: level, word, tone } of levels) {
  test(`needWord and needTone: ${level} pips`, () => assert.deepEqual([needWord(level), needTone(level)], [word, tone]));
}

const merges: { id: string; thoughts: Thought[]; merged: { text: string; mood: number; count: number }[] }[] = [
  { id: "none", thoughts: [], merged: [] },
  { id: "one", thoughts: [thought("Bea took my seat", -6)], merged: [{ text: "Bea took my seat", mood: -6, count: 1 }] },
  { id: "the same text twice is one row with the moods added", thoughts: [thought("Chatted", 3), thought("Chatted", 3)], merged: [{ text: "Chatted", mood: 6, count: 2 }] },
  { id: "rows keep the order they first appeared in", thoughts: [thought("A", 1), thought("B", -2), thought("A", 1)], merged: [{ text: "A", mood: 2, count: 2 }, { text: "B", mood: -2, count: 1 }] },
];
for (const { id, thoughts, merged } of merges) test(`mergeThoughts: ${id}`, () => assert.deepEqual(mergeThoughts(thoughts), merged));

const bars: { id: string; opinion: number; side: string; percent: number }[] = [
  { id: "indifference has no bar", opinion: 0, side: "right", percent: 0 },
  { id: "a friend grows to the right", opinion: 62, side: "right", percent: 31 },
  { id: "dislike grows to the left", opinion: -15, side: "left", percent: 7.5 },
  { id: "the most is half the track", opinion: 100, side: "right", percent: 50 },
  { id: "the least is half the track", opinion: -100, side: "left", percent: 50 },
  { id: "beyond the scale is held", opinion: 150, side: "right", percent: 50 },
];
for (const { id, opinion, side, percent } of bars) test(`opinionBar: ${id}`, () => assert.deepEqual(opinionBar(opinion), { side, percent }));
