import assert from "node:assert/strict";
import { test } from "node:test";
import { reactions, stacked } from "../src/reactions.ts";
import type { Snapshot, Thought, WorldEvent } from "../src/types.ts";

function thought(kind: string, about: string | null, opinion: number, mood = 0, expires = 500): Thought {
  return { kind, about, text: "", mood, opinion, expires_at: expires, source_event: "" };
}

/** Marilyn played; Trump and Putin in the hall with the given thoughts and events at the given time. */
function snapshot(time: number, trump: Thought[], events: WorldEvent[] = [], player: string | null = "marilyn"): Snapshot {
  const guest = (id: string, name: string, thoughts: Thought[] = []) => ({ id, name, thoughts });
  return {
    state: {
      time,
      player: player === null ? null : { actor_id: player, steering: true },
      actors: [guest("marilyn", "Monroe"), guest("trump", "Trump", trump), guest("putin", "Putin")],
      events,
    },
  } as unknown as Snapshot;
}

function answered(type: string, inviter: string, time = 15): WorldEvent {
  return { time, actor_id: "trump", type, message: "", invitation: "darts_together", inviter_id: inviter };
}

test("reactions: the first snapshot replays nothing", () => {
  assert.deepEqual(reactions(null, snapshot(10, [thought("insulted", "marilyn", -15)])), []);
});

test("reactions: no player, no reactions", () => {
  assert.deepEqual(reactions(snapshot(10, [], [], null), snapshot(20, [thought("insulted", "marilyn", -15)], [], null)), []);
});

test("reactions: an empty hall shows nothing", () => {
  const empty = { state: { time: 20, player: { actor_id: "marilyn", steering: true }, actors: [], events: [] } } as unknown as Snapshot;
  assert.deepEqual(reactions(snapshot(10, []), empty), []);
});

test("reactions: a new thought about the player shows over the target, with toasts for the tie and the mood", () => {
  const before = snapshot(10, [thought("chat", "putin", 2)]);
  const after = snapshot(20, [thought("chat", "putin", 2), thought("insulted", "marilyn", -15, -5)]);
  assert.deepEqual(reactions(before, after), [
    { actor_id: "trump", kind: "thought", text: "insulted by Monroe −15" },
    { actor_id: "marilyn", kind: "toast", text: "Trump thinks worse of you −15" },
    { actor_id: "marilyn", kind: "toast", text: "Trump's mood −5" },
  ]);
});

test("reactions: a thought caused by someone else is not shown", () => {
  assert.deepEqual(reactions(snapshot(10, []), snapshot(20, [thought("insulted", "putin", -15, -5)])), []);
});

test("reactions: a thought already held is not shown again", () => {
  const held = [thought("insulted", "marilyn", -15)];
  assert.deepEqual(reactions(snapshot(10, held), snapshot(20, held)), []);
});

test("reactions: a quarrel with the player says it started", () => {
  const after = snapshot(20, [thought("quarrel", "marilyn", -10)]);
  assert.deepEqual(reactions(snapshot(10, []), after).map((item) => item.text),
    ["quarrel by Monroe −10", "Trump thinks worse of you −10", "A quarrel with Trump"]);
});

test("reactions: a thought with no opinion or mood change shows only over the head", () => {
  assert.deepEqual(reactions(snapshot(10, []), snapshot(20, [thought("chat", "marilyn", 0)])),
    [{ actor_id: "trump", kind: "thought", text: "chat by Monroe" }]);
});

const ANSWERS: [string, WorldEvent[], string[]][] = [
  ["the player's invitation accepted", [answered("invitation_accepted", "marilyn")], ["Trump accepted: darts"]],
  ["the player's invitation declined", [answered("invitation_declined", "marilyn")], ["Trump declined: darts"]],
  ["someone else's invitation", [answered("invitation_accepted", "putin")], []],
  ["an answer seen in an earlier snapshot", [answered("invitation_accepted", "marilyn", 10)], []],
  ["an unknown event type", [answered("invitation_pondered", "marilyn")], []],
  ["an answer with an unknown invitation kind", [{ ...answered("invitation_accepted", "marilyn"), invitation: "waltz" }], ["Trump accepted: waltz"]],
];

for (const [name, events, expected] of ANSWERS) {
  test(`reactions: ${name}`, () => {
    assert.deepEqual(reactions(snapshot(10, []), snapshot(20, [], events)).map((item) => item.text), expected);
  });
}

test("reactions: a malformed thought is skipped", () => {
  const bad = { ...thought("insulted", "marilyn", -15), opinion: Number.NaN };
  assert.deepEqual(reactions(snapshot(10, []), snapshot(20, [bad])), []);
});

const GROUPS: [string, { actor_id: string; kind: "thought" | "toast"; text: string }[], [string, string][]][] = [
  ["nothing", [], []],
  ["one", [{ actor_id: "trump", kind: "thought", text: "a" }], [["trump", "a"]]],
  ["two on one figure stack, in order", [{ actor_id: "marilyn", kind: "toast", text: "a" }, { actor_id: "trump", kind: "thought", text: "b" },
    { actor_id: "marilyn", kind: "toast", text: "c" }], [["marilyn", "a\nc"], ["trump", "b"]]],
  ["duplicates collapse", [{ actor_id: "trump", kind: "toast", text: "a" }, { actor_id: "trump", kind: "toast", text: "a" }], [["trump", "a"]]],
];

for (const [name, items, expected] of GROUPS) {
  test(`stacked: ${name}`, () => {
    assert.deepEqual(stacked(items), expected);
  });
}
