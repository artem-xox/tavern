/** Pixel maps: strings of equal length, `.` transparent, any other character a palette key. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { OUTLINE, outlined } from "../src/pixels.ts";

const shapes: { id: string; rows: string[]; outline: string[] }[] = [
  { id: "one pixel gets a plus-shaped outline", rows: ["2"], outline: [".0.", "020", ".0."] },
  { id: "a horizontal pair is ringed on four sides", rows: ["22"], outline: [".00.", "0220", ".00."] },
  { id: "transparent space inside is outlined from the filled side", rows: ["2.2"], outline: [".0.0.", "02020", ".0.0."] },
  { id: "palette keys are kept", rows: ["23"], outline: [".00.", "0230", ".00."] },
  { id: "an empty map stays empty and is padded", rows: ["..."], outline: [".....", ".....", "....."] },
];

for (const { id, rows, outline } of shapes) {
  test(`outlined: ${id}`, () => assert.deepEqual(outlined(rows).map((row: string): string => row.replaceAll(OUTLINE, "0")), outline));
}

test("outlined: no rows give no rows", () => assert.deepEqual(outlined([]), []));

const refused: { id: string; rows: string[]; reason: RegExp }[] = [
  { id: "rows of different lengths", rows: ["22", "2"], reason: /same length/ },
  { id: "a map that uses the outline's own key", rows: ["20"], reason: /outline/ },
];
for (const { id, rows, reason } of refused) test(`outlined: refuses ${id}`, () => assert.throws(() => outlined(rows), reason));
