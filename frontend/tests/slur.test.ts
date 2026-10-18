/** How drink slurs a line in its bubble: the behavior of `src/slur.ts`, one named case per row. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { slur } from "../src/slur.ts";

const LINE = "Believe me, this is the best tavern, simply tremendous.";

const untouched: { id: string; line: string; stage: "sober" | "tipsy" | "drunk" | "wasted" }[] = [
  { id: "a sober guest speaks plainly", line: LINE, stage: "sober" },
  { id: "a tipsy guest still speaks plainly", line: LINE, stage: "tipsy" },
  { id: "an empty line stays empty when drunk", line: "", stage: "drunk" },
  { id: "an empty line stays empty when wasted", line: "", stage: "wasted" },
];
for (const { id, line, stage } of untouched) test(`slur: ${id}`, () => assert.equal(slur(line, stage), line));

const exact: { id: string; line: string; stage: "drunk" | "wasted"; slurred: string }[] = [
  { id: "a drunk one-word line hiccups after it", line: "Cheers!", stage: "drunk", slurred: "Cheersh! *hic*" },
  { id: "a drunk guest slurs only the first s-word", line: "This is mine.", stage: "drunk", slurred: "Thish *hic* is mine." },
  { id: "a capital S slurs to Sh", line: "Sit.", stage: "drunk", slurred: "Shit. *hic*" },
  { id: "an sh already slurred is left alone", line: "Hush now.", stage: "drunk", slurred: "Hush *hic* now." },
];
for (const { id, line, stage, slurred } of exact) test(`slur: ${id}`, () => assert.equal(slur(line, stage), slurred));

test("slur: the same line slurs the same way every time", () => {
  assert.equal(slur(LINE, "wasted"), slur(LINE, "wasted"));
});

const hiccups: { id: string; stage: "drunk" | "wasted"; least: number }[] = [
  { id: "a drunk guest hiccups once", stage: "drunk", least: 1 },
  { id: "a wasted guest hiccups at least twice", stage: "wasted", least: 2 },
];
for (const { id, stage, least } of hiccups) {
  test(`slur: ${id}`, () => {
    const count: number = (slur(LINE, stage).match(/\*hic\*|oops/g) ?? []).length;
    assert.ok(count >= least && count <= least + 1, `${count} in ${slur(LINE, stage)}`);
  });
}

test("slur: a wasted guest slurs every s and drawls the longest word", () => {
  const slurred: string = slur(LINE, "wasted");
  assert.doesNotMatch(slurred.replace(/sh/gi, ""), /s/i);
  assert.match(slurred, /treee/);
});

test("slur: a drunk line keeps every word of the sober one, in order", () => {
  const words: string[] = slur(LINE, "drunk").replace(/\*hic\*/g, "").replace(/sh/g, "s").split(/\s+/).filter(Boolean);
  assert.deepEqual(words, LINE.split(" "));
});
