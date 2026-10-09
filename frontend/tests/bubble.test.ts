/** Speech bubble placement and pacing: the behavior of `src/bubble.ts`, one named case per row. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { callout, chunkAt, chunkMs, newer, placeBubble, splitLine } from "../src/bubble.ts";
import type { WorldEvent } from "../src/types.ts";

const MAP = { width: 640, height: 448 };

const placements: { id: string; speaker: [number, number]; bubble: [number, number]; map: { width: number; height: number };
  placement: { x: number; y: number; originY: 0 | 1 } }[] = [
  { id: "above the speaker when there is room", speaker: [320, 200], bubble: [100, 30], map: MAP, placement: { x: 320, y: 134, originY: 1 } },
  { id: "below the speaker near the top edge", speaker: [320, 50], bubble: [100, 30], map: MAP, placement: { x: 320, y: 72, originY: 0 } },
  { id: "kept inside the left edge", speaker: [0, 200], bubble: [100, 30], map: MAP, placement: { x: 54, y: 134, originY: 1 } },
  { id: "kept inside the right edge", speaker: [640, 200], bubble: [100, 30], map: MAP, placement: { x: 586, y: 134, originY: 1 } },
  { id: "kept above the bottom edge when below", speaker: [320, 200], bubble: [100, 300], map: MAP, placement: { x: 320, y: 144, originY: 0 } },
  { id: "centred when wider than the map", speaker: [10, 200], bubble: [150, 30], map: { width: 100, height: 448 }, placement: { x: 50, y: 134, originY: 1 } },
];
for (const { id, speaker, bubble, map, placement } of placements) {
  test(`placeBubble: ${id}`, () => assert.deepEqual(placeBubble(speaker[0], speaker[1], bubble[0], bubble[1], map), placement));
}

const durations: { id: string; chunk: string; ms: number }[] = [
  { id: "a short piece stays up the least time", chunk: "Aye", ms: 1500 },
  { id: "a piece is read at 15 characters a second", chunk: "x".repeat(30), ms: 2000 },
  { id: "a long piece stays up longer", chunk: "x".repeat(150), ms: 10000 },
  { id: "an ellipsis at either end is not read", chunk: `…${"x".repeat(30)}…`, ms: 2000 },
];
for (const { id, chunk, ms } of durations) test(`chunkMs: ${id}`, () => assert.equal(chunkMs(chunk), ms));

const pieces30: string[] = ["a", "b", "c"].map((letter: string): string => letter.repeat(30));
const due: { id: string; chunks: string[]; elapsedMs: number; index: number }[] = [
  { id: "the first piece at the start", chunks: pieces30, elapsedMs: 0, index: 0 },
  { id: "still the first just before its time ends", chunks: pieces30, elapsedMs: 1999, index: 0 },
  { id: "the second as the first ends", chunks: pieces30, elapsedMs: 2000, index: 1 },
  { id: "the last as the second ends", chunks: pieces30, elapsedMs: 4000, index: 2 },
  { id: "the last one for as long as it takes", chunks: pieces30, elapsedMs: 99999, index: 2 },
  { id: "the only piece of a one-piece line", chunks: ["Aye"], elapsedMs: 5000, index: 0 },
];
for (const { id, chunks, elapsedMs, index } of due) test(`chunkAt: ${id}`, () => assert.equal(chunkAt(chunks, elapsedMs), index));

const lines: { id: string; line: string; pieces: string[] }[] = [
  { id: "an empty line has no pieces", line: "", pieces: [] },
  { id: "only spaces has no pieces", line: "   ", pieces: [] },
  { id: "one word is one piece", line: "Aye", pieces: ["Aye"] },
  { id: "two short sentences share a piece", line: "Evening. What'll it be?", pieces: ["Evening. What'll it be?"] },
  { id: "a sentence without an end mark is one piece", line: "Aye. Fine", pieces: ["Aye. Fine"] },
  { id: "an ellipsis inside a line does not split a short one", line: "Well... I suppose so.", pieces: ["Well... I suppose so."] },
  { id: "extra spaces are squeezed", line: "Aye.   Fine.", pieces: ["Aye. Fine."] },
  { id: "sentences are never cut apart while they fit", line: `${"a".repeat(39)}. ${"b".repeat(39)}. ${"c".repeat(39)}.`,
    pieces: [`${"a".repeat(39)}. ${"b".repeat(39)}.`, `${"c".repeat(39)}.`] },
  { id: "a closing quote after the full stop still ends the sentence",
    line: 'He shouted "Get out of my sight, you thieving, lying wretch." Then he sat down again by the fire and sulked.',
    pieces: ['He shouted "Get out of my sight, you thieving, lying wretch."', "Then he sat down again by the fire and sulked."] },
  { id: "a sentence over the limit is cut at a comma and joined by ellipses",
    line: "The margrave has been abed with a fever for a week, and the manor kitchen is told to send up nothing but broth.",
    pieces: ["The margrave has been abed with a fever for a week,…", "…and the manor kitchen is told to send up nothing but broth."] },
  { id: "the sentence after a cut one joins its last part when it fits",
    line: "The margrave has been abed with a fever for a week, and the manor kitchen is told to send up nothing but broth. Evening.",
    pieces: ["The margrave has been abed with a fever for a week,…", "…and the manor kitchen is told to send up nothing but broth. Evening."] },
  { id: "a long line with no punctuation is cut in even halves",
    line: Array.from({ length: 30 }, (): string => "aaaa").join(" "),
    pieces: [`${Array.from({ length: 15 }, (): string => "aaaa").join(" ")}…`, `…${Array.from({ length: 15 }, (): string => "aaaa").join(" ")}`] },
];
for (const { id, line, pieces } of lines) test(`splitLine: ${id}`, () => assert.deepEqual(splitLine(line), pieces));

function call(actor: string | null, time: number, line: string | null = "Time, friends!", type: string = "last_call"): WorldEvent {
  return { time, actor_id: actor, type, message: `called out: ${line}`, ...(line === null ? {} : { line }) };
}

const callouts: { id: string; events: WorldEvent[]; at: number; said: { speaker: string; line: string; time: number } | null }[] = [
  { id: "no events", events: [], at: 541, said: null },
  { id: "another character's call", events: [call("rurik", 540)], at: 541, said: null },
  { id: "a call 3 seconds ago", events: [call("hob", 540)], at: 543, said: { speaker: "hob", line: "Time, friends!", time: 540 } },
  { id: "a call 9 seconds ago is over", events: [call("hob", 540)], at: 549, said: null },
  { id: "the newest of two calls", events: [call("hob", 100, "First."), call("hob", 540, "Second.")], at: 542, said: { speaker: "hob", line: "Second.", time: 540 } },
  { id: "another kind of event with a line", events: [call("hob", 540, "Hello.", "conversation")], at: 541, said: null },
  { id: "a call with no words", events: [call("hob", 540, null)], at: 541, said: null },
  { id: "a call by nobody (the innkeeper without a barkeep)", events: [call(null, 540)], at: 541, said: null },
];
for (const { id, events, at, said } of callouts) test(`callout: ${id}`, () => assert.deepEqual(callout(events, "hob", at), said));

const own = { speaker: "hob", line: "Evening.", time: 538 };
const shout = { speaker: "hob", line: "Time, friends!", time: 540 };
const newest: { id: string; chat: typeof own | null; called: typeof own | null; said: typeof own | null }[] = [
  { id: "only a chat line", chat: own, called: null, said: own },
  { id: "only the call", chat: null, called: shout, said: shout },
  { id: "the call after a chat line", chat: own, called: shout, said: shout },
  { id: "a chat line after the call", chat: { ...own, time: 545 }, called: shout, said: { ...own, time: 545 } },
  { id: "nothing said", chat: null, called: null, said: null },
];
for (const { id, chat, called, said } of newest) test(`newer: ${id}`, () => assert.deepEqual(newer(chat, called), said));
