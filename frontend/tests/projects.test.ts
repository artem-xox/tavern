/** How the inspector words a plan under way: the behavior of `src/projects.ts`, one named case per row. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { projectLabel } from "../src/projects.ts";

const labels: { id: string; kind: string; step: number; of: number; label: string }[] = [
  { id: "the first step", kind: "settle_in", step: 0, of: 3, label: "Plan · settle in, step 1 of 3" },
  { id: "the last step", kind: "settle_in", step: 2, of: 3, label: "Plan · settle in, step 3 of 3" },
  { id: "a step past the end is held at the last", kind: "settle_in", step: 5, of: 3, label: "Plan · settle in, step 3 of 3" },
];
for (const { id, kind, step, of, label } of labels) {
  test(`projectLabel: ${id}`, () => assert.equal(projectLabel(kind, step, of), label));
}
