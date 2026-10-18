/** The faint haze over a drunk guest: the behavior of `src/aura.ts`, one named case per row. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { aura, AURA_TOP, AURA_BOTTOM } from "../src/aura.ts";

const counts: { id: string; stage: "sober" | "tipsy" | "drunk" | "wasted"; motes: number; glows: boolean }[] = [
  { id: "a sober guest has no haze", stage: "sober", motes: 0, glows: false },
  { id: "a tipsy guest has no haze yet", stage: "tipsy", motes: 0, glows: false },
  { id: "a drunk guest has a glow and a few bubbles", stage: "drunk", motes: 3, glows: true },
  { id: "a wasted guest has more bubbles", stage: "wasted", motes: 5, glows: true },
];
for (const { id, stage, motes, glows } of counts) {
  test(`aura: ${id}`, () => {
    const haze = aura(stage, 1234, 0.3);
    assert.equal(haze.motes.length, motes);
    assert.equal(haze.glow > 0, glows);
  });
}

test("aura: it stays faint and above the feet for a whole cycle", () => {
  for (let time = 0; time < 6000; time += 97) {
    const haze = aura("wasted", time, 0.7);
    assert.ok(haze.glow > 0 && haze.glow <= 0.25, `glow ${haze.glow} at ${time}`);
    for (const mote of haze.motes) {
      assert.ok(mote.y <= AURA_BOTTOM && mote.y >= AURA_TOP, `y ${mote.y} at ${time}`);
      assert.ok(mote.alpha >= 0 && mote.alpha <= 0.6, `alpha ${mote.alpha} at ${time}`);
      assert.ok(Math.abs(mote.x) <= 22, `x ${mote.x} at ${time}`);
    }
  }
});

test("aura: the bubbles rise over time", () => {
  assert.ok(aura("drunk", 100, 0).motes[0]!.y < aura("drunk", 0, 0).motes[0]!.y);
});

test("aura: two guests' hazes are out of step", () => {
  assert.notDeepEqual(aura("drunk", 500, 0), aura("drunk", 500, 0.5));
});
