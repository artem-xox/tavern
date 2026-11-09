import assert from "node:assert/strict";
import { test } from "node:test";
import { readingOf, refusedTurns } from "../src/readings.ts";
import type { Turn, WorldEvent } from "../src/types.ts";

const NAMES = new Map<string, string>([["trump", "Trump"], ["monroe", "Monroe"]]);
const nameOf = (id: string): string => NAMES.get(id) ?? id;

function turn(act: string, addressee: string | null, extra: Partial<Turn> = {}): Turn {
  return { speaker: "marilyn", addressee, line: "words", act, time: 10, ...extra };
}

const CHIPS: [string, Turn, { text: string; refused: boolean } | null][] = [
  ["an insult read as meant names its target", turn("insult", "trump"), { text: "insult → Trump", refused: false }],
  ["an invitation names its kind", turn("invite", "monroe", { invitation: "darts_together" }), { text: "invitation: darts → Monroe", refused: false }],
  ["news to nobody in particular goes to everyone", turn("share_news", null, { fact_id: "f1" }), { text: "news → everyone", refused: false }],
  ["an unknown act shows in plain words", turn("sing_loudly", "trump"), { text: "sing loudly → Trump", refused: false }],
  ["a silence has no reading", turn("silence", null), null],
  ["a malformed act has no reading", turn("", "trump"), null],
];

for (const [name, item, expected] of CHIPS) {
  test(`readingOf: ${name}`, () => {
    assert.deepEqual(readingOf(item, false, nameOf), expected);
  });
}

test("readingOf: a refused reading shows as a bare remark", () => {
  assert.deepEqual(readingOf(turn("remark", "trump"), true, nameOf), { text: "remark", refused: true });
});

function misread(time: number, speaker: string): WorldEvent {
  return { time, actor_id: speaker, type: "misread", message: "", speaker_id: speaker };
}

const REFUSALS: [string, Turn[], WorldEvent[], number[]][] = [
  ["no turns", [], [misread(5, "marilyn")], []],
  ["no misread", [turn("remark", null, { time: 10 })], [], []],
  ["a misread before the player's line refuses it",
    [turn("remark", null, { time: 10 })], [misread(8, "marilyn")], [0]],
  ["a misread refuses only the player's next line",
    [turn("remark", null, { time: 4 }), turn("remark", null, { time: 10 }), turn("remark", null, { time: 20 })],
    [misread(8, "marilyn")], [1]],
  ["another speaker's line is not the player's",
    [turn("remark", null, { time: 10, speaker: "trump" })], [misread(8, "marilyn")], []],
  ["another speaker's misread does not count",
    [turn("remark", null, { time: 10 })], [misread(8, "trump")], []],
  ["a misread line that was not spoken as a remark is not refused",
    [turn("insult", "trump", { time: 10 })], [misread(8, "marilyn")], []],
];

for (const [name, turns, events, expected] of REFUSALS) {
  test(`refusedTurns: ${name}`, () => {
    assert.deepEqual([...refusedTurns(turns, events, "marilyn")], expected);
  });
}
