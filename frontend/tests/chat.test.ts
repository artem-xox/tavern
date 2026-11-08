import assert from "node:assert/strict";
import { test } from "node:test";
import { chatModel, nextPing, sayCommand } from "../src/chat.ts";
import type { PlayerTurn, Snapshot } from "../src/types.ts";

const SILENT: PlayerTurn = { scene_id: null, state: "none", silence_at: null };

/** A snapshot of Monroe in a scene with Putin and Trump: Putin spoke, Trump kept silent, Monroe spoke to everyone. */
function snapshot(turn: PlayerTurn | null, speed = 1, time = 100, steering = true): Snapshot {
  const guest = (id: string) => ({ id, name: id.toUpperCase(), sprite: `${id}-art` });
  const line = (speaker: string, addressee: string | null, text: string, act = "remark") => ({ speaker, addressee, line: text, act });
  return {
    player_turn: turn,
    state: {
      time, speed,
      player: turn === null ? null : { actor_id: "monroe", steering },
      actors: [guest("monroe"), guest("putin"), guest("trump"), guest("bea")],
      conversations: [
        { id: "c1", participants: ["monroe", "putin", "trump"], turns: [
          line("putin", "monroe", "Marilyn."), line("trump", null, "", "silence"), line("monroe", null, "Hello, all."),
        ] },
        { id: "c2", participants: ["bea"], turns: [] },
      ],
    },
  } as unknown as Snapshot;
}

test("chatModel: no player, no chat", () => {
  assert.equal(chatModel(snapshot(null)), null);
});

test("chatModel: outside a scene the input is off and says how to talk", () => {
  const model = chatModel(snapshot(SILENT));
  assert.deepEqual([model?.enabled, model?.lines, model?.members, model?.placeholder],
    [false, [], [], "Click someone and choose Talk"]);
});

test("chatModel: autopilot turns the input off even in a scene", () => {
  const model = chatModel(snapshot({ scene_id: "c1", state: "none", silence_at: null }, 1, 100, false));
  assert.equal(model?.enabled, false);
});

test("chatModel: a scene of three shows the others and the lines, a silence as an ellipsis", () => {
  const model = chatModel(snapshot({ scene_id: "c1", state: "free", silence_at: null }));
  assert.deepEqual(model?.members, [{ id: "putin", name: "PUTIN", face: "putin-art" }, { id: "trump", name: "TRUMP", face: "trump-art" }]);
  assert.deepEqual(model?.lines.map((item) => [item.speaker, item.addressee, item.words, item.mine]),
    [["PUTIN", "MONROE", "Marilyn.", false], ["TRUMP", null, "…", false], ["MONROE", null, "Hello, all.", true]]);
  assert.deepEqual([model?.enabled, model?.state, model?.secondsLeft, model?.picker], [true, "free", null, true]);
});

test("chatModel: the player's turn counts real seconds, a faster world fewer of them", () => {
  const turn: PlayerTurn = { scene_id: "c1", state: "your_turn", silence_at: 140 };
  assert.deepEqual([chatModel(snapshot(turn))?.secondsLeft, chatModel(snapshot(turn, 2))?.secondsLeft], [40, 20]);
  assert.equal(chatModel(snapshot(turn, 1, 150))?.secondsLeft, 0);
  assert.equal(chatModel(snapshot(turn))?.placeholder, "Your turn");
});

test("chatModel: reading, the stage and a comeback change the input", () => {
  const model = (state: PlayerTurn["state"]) => chatModel(snapshot({ scene_id: "c1", state, silence_at: null }));
  assert.deepEqual([model("reading")?.enabled, model("reading")?.picker], [false, true]);
  assert.deepEqual([model("on_stage")?.placeholder, model("on_stage")?.picker, model("on_stage")?.enabled], ["Speak to the hall", false, true]);
  assert.equal(model("comeback")?.placeholder, "Answer the heckler");
});

test("nextPing: at most every two seconds, while focused with text", () => {
  assert.deepEqual([
    nextPing(null, 0, true, true), nextPing(0, 1.9, true, true), nextPing(0, 2, true, true),
    nextPing(null, 5, false, true), nextPing(null, 5, true, false),
  ], [true, false, true, false, false]);
});

test("sayCommand: trims the text and carries the addressee", () => {
  assert.deepEqual(sayCommand("  Hello there  ", "auto"), { type: "say", text: "Hello there", to: "auto" });
  assert.deepEqual(sayCommand("Hi", "everyone"), { type: "say", text: "Hi", to: "everyone" });
  assert.deepEqual(sayCommand("Hi", "putin"), { type: "say", text: "Hi", to: "putin" });
  assert.equal(sayCommand("   ", "auto"), null);
});
