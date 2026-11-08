import assert from "node:assert/strict";
import { test } from "node:test";
import { roleSheet } from "../src/rolesheet.ts";
import type { Actor } from "../src/types.ts";

/** A guest with just what the sheet reads. */
function guest(fields: Partial<Actor>): Actor {
  return { id: "monroe", name: "Marilyn Monroe", card: null, ties: [], relations: {}, ...fields } as unknown as Actor;
}

const card = { occupation: "a film star", temperament: "Warm and wary.", speech: "Breathy.", quirks: "Hums.",
  obsessions: ["be seen", "a quiet drink"], catchphrases: ["Darling."] };

test("roleSheet: persona, obsessions and catchphrases come from the card", () => {
  const sheet = roleSheet(guest({ card: card as unknown as Actor["card"] }));
  assert.deepEqual(sheet.persona, [["Who", "a film star"], ["Temper", "Warm and wary."], ["Speech", "Breathy."], ["Quirks", "Hums."]]);
  assert.deepEqual([sheet.obsessions, sheet.catchphrases], [["be seen", "a quiet drink"], ["Darling."]]);
});

test("roleSheet: a guest with no card and no ties has an empty sheet", () => {
  assert.deepEqual(roleSheet(guest({})), { persona: [], obsessions: [], catchphrases: [], rivals: [] });
});

test("roleSheet: rivals are the rival and bad-blood ties and the people they think ill of, each once, by name", () => {
  const sheet = roleSheet(guest({
    ties: [
      { with: "putin", name: "Putin", kind: "rivals", note: "Both want the head seat." },
      { with: "trump", name: "Trump", kind: "old friends", note: "Golf." },
      { with: "kim", name: "Kim", kind: "bad blood", note: "A cheque." },
    ],
    relations: {
      putin: { name: "Putin", opinion: -30, familiarity: "friend" },
      trump: { name: "Trump", opinion: 20, familiarity: "friend" },
      hob: { name: "the barkeep", opinion: -10, familiarity: "stranger" },
    },
  }));
  assert.deepEqual(sheet.rivals, [
    { name: "Putin", why: "Both want the head seat." },
    { name: "Kim", why: "A cheque." },
    { name: "the barkeep", why: "" },
  ]);
});
