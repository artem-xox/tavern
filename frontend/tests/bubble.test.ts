/** Speech bubble placement and pacing: the behavior of `src/bubble.ts`, one named case per row. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { chunkAt, chunkMs, placeBubble, splitLine } from "../src/bubble.ts";

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
];
for (const { id, line, pieces } of lines) test(`splitLine: ${id}`, () => assert.deepEqual(splitLine(line), pieces));
