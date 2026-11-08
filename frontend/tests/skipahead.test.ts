import assert from "node:assert/strict";
import { test } from "node:test";
import { canSkip, SKIP_CAP, skipFrom, skipStop, type Skip } from "../src/skipahead.ts";
import type { PlayerTurn, Snapshot, WorldEvent } from "../src/types.ts";

interface Hall {
  state?: PlayerTurn["state"];
  events?: Partial<WorldEvent>[];
  time?: number;
  steering?: boolean;
  player?: boolean;
  paused?: boolean;
  held?: boolean;
}

/** Monroe, played, in a hall at game time `time` (default 130), with the events given. */
function snapshot(hall: Hall = {}): Snapshot {
  return {
    player_turn: hall.player === false ? null : { scene_id: null, state: hall.state ?? "none", silence_at: null },
    turn_held: hall.held ?? false,
    state: {
      time: hall.time ?? 130, speed: 8, paused: hall.paused ?? false,
      player: hall.player === false ? null : { actor_id: "monroe", steering: hall.steering ?? true },
      events: (hall.events ?? []).map((event) => ({ time: 120, actor_id: "putin", type: "turn", message: "", ...event })),
    },
  } as unknown as Snapshot;
}

const SKIP: Skip = { since: 100, speed: 1 };

test("skipFrom: starts at the world's time and remembers the speed to come back to", () => {
  assert.deepEqual(skipFrom({ ...snapshot({ time: 100 }).state, speed: 1 }), SKIP);
});

const cases: { id: string; hall: Hall; stop: ReturnType<typeof skipStop> }[] = [
  { id: "quiet-hall", hall: {}, stop: null },
  { id: "line-to-someone-else", hall: { events: [{ act: "remark", addressee: "trump" }] }, stop: null },
  { id: "line-to-everyone", hall: { events: [{ act: "remark", addressee: null }] }, stop: null },
  { id: "line-to-the-player", hall: { events: [{ act: "remark", addressee: "monroe" }] }, stop: "addressed" },
  { id: "old-line-to-the-player", hall: { events: [{ act: "remark", addressee: "monroe", time: 90 }] }, stop: null },
  { id: "own-line", hall: { events: [{ actor_id: "monroe", act: "remark", addressee: "putin" }] }, stop: null },
  { id: "invitation-to-the-player", hall: { events: [{ act: "invite", addressee: "monroe" }] }, stop: "invited" },
  { id: "quarrel-in-the-hall", hall: { events: [{ type: "quarrel" }] }, stop: "quarrel" },
  { id: "fight-in-the-hall", hall: { events: [{ type: "fight_started" }] }, stop: "fight" },
  { id: "old-fight", hall: { events: [{ type: "fight_started", time: 50 }] }, stop: null },
  { id: "players-turn", hall: { state: "your_turn" }, stop: "your_turn" },
  { id: "comeback-owed", hall: { state: "comeback" }, stop: "your_turn" },
  { id: "someone-else-speaks", hall: { state: "free" }, stop: null },
  { id: "cap-reached", hall: { time: 100 + SKIP_CAP }, stop: "cap" },
  { id: "autopilot", hall: { steering: false }, stop: "over" },
  { id: "no-player", hall: { player: false }, stop: "over" },
  { id: "paused-by-hand", hall: { paused: true }, stop: "over" },
  { id: "held-for-a-line", hall: { paused: true, held: true, state: "your_turn" }, stop: "your_turn" },
];

for (const item of cases) {
  test(`skipStop: ${item.id}`, () => {
    assert.equal(skipStop(SKIP, snapshot(item.hall)), item.stop);
  });
}

test("skipStop: a shorter cap stops sooner", () => {
  assert.equal(skipStop(SKIP, snapshot({ time: 130 }), 30), "cap");
});

const starts: { id: string; hall: Hall; can: boolean }[] = [
  { id: "hall-running", hall: {}, can: true },
  { id: "paused", hall: { paused: true }, can: false },
  { id: "line-due", hall: { state: "your_turn" }, can: false },
  { id: "autopilot", hall: { steering: false }, can: false },
  { id: "no-player", hall: { player: false }, can: false },
];

for (const item of starts) {
  test(`canSkip: ${item.id}`, () => {
    assert.equal(canSkip(snapshot(item.hall)), item.can);
  });
}
