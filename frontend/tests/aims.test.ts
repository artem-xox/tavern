/** How the inspector words the aim of a social option: the behavior of `src/aims.ts`, one named case per row. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { aimLabel } from "../src/aims.ts";

const labels: { id: string; aim: string; label: string }[] = [
  { id: "a plain aim", aim: "pass_time", label: "pass time" },
  { id: "news names its topic's id", aim: "tell_news:margrave_fever", label: "tell news: margrave fever" },
  { id: "an invitation names its kind", aim: "invite:dice_together", label: "invite: dice together" },
  { id: "a rematch", aim: "rematch", label: "rematch" },
];
for (const { id, aim, label } of labels) {
  test(`aimLabel: ${id}`, () => assert.equal(aimLabel(aim), label));
}

test("aimLabel: an empty aim is an empty label", () => assert.equal(aimLabel(""), ""));
