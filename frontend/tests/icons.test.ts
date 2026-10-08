/** Item icons: pixel pictures keyed by item kind, with a bundle for a kind that has none. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { iconPixels } from "../src/icons.ts";

const kinds: { id: string; kind: string }[] = [
  { id: "a mug of ale", kind: "beer" },
  { id: "a herbal remedy", kind: "remedy" },
  { id: "a keepsake", kind: "keepsake" },
  { id: "a kind with no picture of its own", kind: "coins" },
];

for (const { id, kind } of kinds) {
  test(`iconPixels: ${id} is a square of coloured pixels inside its size`, () => {
    const icon = iconPixels(kind);
    assert.equal(icon.size, 18, "16 pixels and a ring of outline");
    assert.ok(icon.pixels.length > 40, "it draws something");
    for (const pixel of icon.pixels) {
      assert.ok(pixel.x >= 0 && pixel.x < icon.size && pixel.y >= 0 && pixel.y < icon.size, `${pixel.x},${pixel.y} is outside`);
      assert.match(pixel.color, /^#[0-9a-f]{6}$/i);
    }
  });
}

test("iconPixels: the three kinds look different from each other", () => {
  const looks = ["beer", "remedy", "keepsake"].map((kind: string): string => JSON.stringify(iconPixels(kind).pixels));
  assert.equal(new Set(looks).size, 3);
});

test("iconPixels: a kind with no picture gets the bundle", () => {
  assert.deepEqual(iconPixels("coins"), iconPixels("anything else"));
  assert.notDeepEqual(iconPixels("coins"), iconPixels("beer"));
});

test("iconPixels: every icon has a dark outline pixel on its edge", () => {
  for (const { kind } of kinds) {
    const dark = iconPixels(kind).pixels.filter((pixel) => pixel.color.toLowerCase() === "#1b120d");
    assert.ok(dark.length > 10, `${kind} has no outline`);
  }
});
