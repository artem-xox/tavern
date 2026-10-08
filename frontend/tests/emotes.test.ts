/** What an emote shows: its picture frame, its pop-in and its drift, as functions of time. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { EMOTE_KINDS, EMOTE_WORDS, emoteFrame, emoteMotion, emoteFrames } from "../src/emotes.ts";
import type { EmoteKind } from "../src/types.ts";

const frames: { id: string; kind: EmoteKind; time: number; frame: number }[] = [
  { id: "a still emote has one frame", kind: "alert", time: 123456, frame: 0 },
  { id: "waiting starts with the first dot lit", kind: "waiting", time: 0, frame: 0 },
  { id: "waiting lights the second dot after a beat", kind: "waiting", time: 350, frame: 1 },
  { id: "waiting lights the third dot", kind: "waiting", time: 700, frame: 2 },
  { id: "waiting starts over", kind: "waiting", time: 1050, frame: 0 },
];
for (const { id, kind, time, frame } of frames) test(`emoteFrame: ${id}`, () => assert.equal(emoteFrame(kind, time), frame));

const pops: { id: string; sinceMs: number; scale: number }[] = [
  { id: "nothing at the first instant", sinceMs: 0, scale: 0 },
  { id: "overshoots at 60% of the pop", sinceMs: 120, scale: 1.2 },
  { id: "settles by the end", sinceMs: 200, scale: 1 },
  { id: "stays settled", sinceMs: 5000, scale: 1 },
];
for (const { id, sinceMs, scale } of pops) {
  test(`emoteMotion: pop, ${id}`, () => assert.ok(Math.abs(emoteMotion("alert", sinceMs, 0).scale - scale) < 1e-9));
}

test("emoteMotion: a settled emote bobs by one pixel at most, in whole pixels", () => {
  for (let time = 0; time < 4000; time += 50) {
    const lift = emoteMotion("alert", 5000, time).lift;
    assert.ok(lift === 0 || lift === 1, `lift ${lift} at ${time}`);
  }
});

test("emoteMotion: a sleeping emote drifts up and fades, then starts over", () => {
  const start = emoteMotion("sleep", 5000, 0);
  const late = emoteMotion("sleep", 5000, 1700);
  const again = emoteMotion("sleep", 5000, 2000);
  assert.ok(late.lift > start.lift, "it rises");
  assert.ok(late.alpha < start.alpha, "it fades");
  assert.equal(again.alpha, start.alpha);
  assert.equal(again.lift, start.lift);
});

test("emoteMotion: other emotes stay opaque", () => assert.equal(emoteMotion("angry", 5000, 777).alpha, 1));

test("every emote kind the server sends has pictures and a word", () => {
  for (const kind of EMOTE_KINDS) {
    assert.ok(emoteFrames(kind).length >= 1, `${kind} has no picture`);
    assert.ok(EMOTE_WORDS[kind].length > 0, `${kind} has no word`);
  }
});
