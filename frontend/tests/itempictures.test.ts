/** Signature items are drawn from picture files, and every other kind from a pixel map. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { iconPixels, itemPicture } from "../src/icons.ts";

const SIGNATURE: string[] = ["phone", "protest_sign", "microphone"];

for (const kind of SIGNATURE) {
  test(`itemPicture: ${kind} has a picture file that ships with the client`, () => {
    const url: string | null = itemPicture(kind);
    assert.ok(url, `${kind} has no picture`);
    assert.ok(existsSync(new URL(`../static${url}`, import.meta.url)), `${url} is not in static/`);
  });
}

for (const kind of ["beer", "remedy", "keepsake", "coins"]) {
  test(`itemPicture: ${kind} is drawn from its pixel map, not a file`, () => {
    assert.equal(itemPicture(kind), null);
    assert.ok(iconPixels(kind).pixels.length > 0);
  });
}
