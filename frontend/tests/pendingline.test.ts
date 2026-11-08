import assert from "node:assert/strict";
import { test } from "node:test";
import { pendingLine, pendingSpoken, settle, type PendingLine } from "../src/pendingline.ts";
import type { PlayerTurn, Snapshot } from "../src/types.ts";

interface Hall {
  state?: PlayerTurn["state"];
  scene?: string | null;
  turns?: { speaker: string }[];
  participants?: string[];
  events?: { actor_id: string | null; line?: string; time: number }[];
  steering?: boolean;
  time?: number;
}

/** Monroe, played, in scene c1 with Putin; the turns and events as given. */
function snapshot(hall: Hall = {}): Snapshot {
  const scene: string | null = hall.scene === undefined ? "c1" : hall.scene;
  return {
    player_turn: { scene_id: scene, state: hall.state ?? "reading", silence_at: null },
    state: {
      time: hall.time ?? 50,
      player: { actor_id: "monroe", steering: hall.steering ?? true },
      conversations: scene === null ? [] : [{ id: scene, participants: hall.participants ?? ["monroe", "putin"],
        turns: (hall.turns ?? [{ speaker: "putin" }]).map((turn) => ({ ...turn, line: "…", act: "remark", addressee: null })) }],
      events: (hall.events ?? []).map((event) => ({ ...event, type: "heckle_answered", message: "" })),
    },
  } as unknown as Snapshot;
}

const SENT: PendingLine = { text: "Hello, Vladimir.", sceneId: "c1", turns: 1, sentAt: 50 };
const STAGE: PendingLine = { text: "Get off!", sceneId: null, turns: 0, sentAt: 50 };

test("pendingLine: remembers the scene and how many turns it had", () => {
  assert.deepEqual(pendingLine("Hello, Vladimir.", snapshot({ state: "your_turn" })), SENT);
});

test("pendingLine: a line from the stage has no scene", () => {
  assert.deepEqual(pendingLine("Get off!", snapshot({ state: "comeback", scene: null })), STAGE);
});

const cases: { id: string; pending: PendingLine | null; hall: Hall; waits: boolean }[] = [
  { id: "nothing-pending", pending: null, hall: {}, waits: false },
  { id: "still-being-read", pending: SENT, hall: {}, waits: true },
  { id: "someone-else-spoke", pending: SENT, hall: { turns: [{ speaker: "putin" }, { speaker: "putin" }] }, waits: true },
  { id: "own-earlier-turn", pending: SENT, hall: { turns: [{ speaker: "monroe" }] }, waits: true },
  { id: "turn-landed", pending: SENT, hall: { turns: [{ speaker: "putin" }, { speaker: "monroe" }] }, waits: false },
  { id: "scene-ended", pending: SENT, hall: { scene: null, state: "none" }, waits: false },
  { id: "left-the-scene", pending: SENT, hall: { participants: ["putin"] }, waits: false },
  { id: "autopilot", pending: SENT, hall: { steering: false }, waits: false },
  { id: "stage-waiting", pending: STAGE, hall: { scene: null, state: "comeback" }, waits: true },
  { id: "stage-answered", pending: STAGE, hall: { scene: null, state: "comeback", events: [{ actor_id: "monroe", line: "Get off!", time: 51 }] }, waits: false },
  { id: "stage-older-same-words", pending: STAGE, hall: { scene: null, state: "comeback", events: [{ actor_id: "monroe", line: "Get off!", time: 10 }] }, waits: true },
  { id: "stage-left", pending: STAGE, hall: { scene: null, state: "none" }, waits: false },
];

for (const item of cases) {
  test(`settle: ${item.id}`, () => {
    assert.equal(settle(item.pending, snapshot(item.hall)) !== null, item.waits);
  });
}

test("pendingSpoken: the line as a bubble over the played guest, at the time it was sent", () => {
  assert.deepEqual(pendingSpoken(SENT, "monroe"), { speaker: "monroe", line: "Hello, Vladimir.", time: 50 });
});
