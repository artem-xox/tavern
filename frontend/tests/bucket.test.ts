/** The privy's bucket: a pixel map of a stave bucket, hooped with iron, with an iron bail and one tall stave. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { BUCKET_PALETTE, bucketRows } from "../src/bucket.ts";
import { OUTLINE } from "../src/pixels.ts";

const rows: string[] = bucketRows();
const count = (key: string): number => rows.join("").split(key).length - 1;
const bands = (key: string): number => rows.filter((row: string): boolean => row.includes(key)).length;

test("bucketRows: rows are equal in length and the map is the size of a small object in a 32 px cell", () => {
  assert.ok(rows.every((row: string): boolean => row.length === rows[0]!.length));
  assert.ok(rows[0]!.length <= 28 && rows.length <= 32);
});

test("bucketRows: every key used has a colour, the outline included", () => {
  const keys: Set<string> = new Set(rows.join("").replaceAll(".", ""));
  assert.deepEqual([...keys].filter((key: string): boolean => !(key in BUCKET_PALETTE)), []);
  assert.ok(keys.has(OUTLINE));
});

test("bucketRows: a dark mouth, iron hoops on the staves, an iron handle and a lighter rim are all there", () => {
  assert.ok(count("i") > 20, "mouth");
  assert.ok(bands("s") >= 6, "two hoops, each some rows tall");
  assert.ok(count("S") > 15 && count("d") > 15, "hoops lit above and shadowed below");
  assert.ok(count("r") > 10, "rim");
  assert.ok(count("w") > 3, "the tall stave");
});

test("bucketRows: the left of the body is lit and the right is in shade", () => {
  const body: string[] = rows.slice(Math.floor(rows.length * 0.6), Math.floor(rows.length * 0.75));
  const lit = (side: string[]): number => side.join("").split("").filter((key: string): boolean => key === "h").length;
  const half: number = Math.floor(rows[0]!.length / 2);
  assert.ok(lit(body.map((row: string): string => row.slice(0, half))) > lit(body.map((row: string): string => row.slice(half))));
});
