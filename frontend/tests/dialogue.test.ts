import assert from "node:assert/strict";
import { test } from "node:test";
import { CLOSED, dialogueStep, type DialogueEvent, type DialogueState } from "../src/dialogue.ts";
import type { PlayerTurn } from "../src/types.ts";

const seen = (scene: string | null, turn: PlayerTurn["state"], steering = true): DialogueEvent =>
  ({ kind: "snapshot", scene, turn, steering });
const open = (to: string, scene: string | null, turn: PlayerTurn["state"]): DialogueState => ({ open: true, to, scene, turn });
const shut = (to: string, scene: string | null, turn: PlayerTurn["state"]): DialogueState => ({ open: false, to, scene, turn });

/** Each case: the state before, the event, the state after. */
for (const [name, before, event, after] of [
  ["no scene stays closed", CLOSED, seen(null, "none"), shut("auto", null, "none")],
  ["a scene starting opens, addressed to auto", CLOSED, seen("c1", "free"), open("auto", "c1", "free")],
  ["a scene starting on autopilot stays closed", CLOSED, seen("c1", "none", false), shut("auto", null, "none")],
  ["taking the wheel mid-scene opens it", shut("auto", null, "none"), seen("c1", "free"), open("auto", "c1", "free")],
  ["the same scene going on keeps it open and the addressee", open("putin", "c1", "free"), seen("c1", "free"), open("putin", "c1", "free")],
  ["closed with Esc, the same scene does not reopen it", shut("auto", "c1", "free"), seen("c1", "free"), shut("auto", "c1", "free")],
  ["the turn coming reopens it at auto", shut("putin", "c1", "free"), seen("c1", "your_turn"), open("auto", "c1", "your_turn")],
  ["the turn coming while open keeps the addressee", open("putin", "c1", "free"), seen("c1", "your_turn"), open("putin", "c1", "your_turn")],
  ["the same turn going on after Esc stays closed", shut("auto", "c1", "your_turn"), seen("c1", "your_turn"), shut("auto", "c1", "your_turn")],
  ["the line being read after sending stays closed", shut("auto", "c1", "your_turn"), seen("c1", "reading"), shut("auto", "c1", "reading")],
  ["a comeback owed opens it", CLOSED, seen(null, "comeback"), open("auto", null, "comeback")],
  ["climbing the stage opens it", CLOSED, seen(null, "on_stage"), open("auto", null, "on_stage")],
  ["a new scene resets the addressee", open("putin", "c1", "free"), seen("c2", "free"), open("auto", "c2", "free")],
  ["the scene ending closes it", open("putin", "c1", "free"), seen(null, "none"), shut("auto", null, "none")],
  ["taking autopilot closes it", open("putin", "c1", "free"), seen("c1", "none", false), shut("auto", null, "none")],
  ["Esc closes it", open("putin", "c1", "free"), { kind: "close" }, shut("putin", "c1", "free")],
  ["sending closes it", open("putin", "c1", "your_turn"), { kind: "sent" }, shut("putin", "c1", "your_turn")],
  ["a refused line reopens it", shut("putin", "c1", "reading"), { kind: "failed" }, open("putin", "c1", "reading")],
  ["a click on a member reopens it to them", shut("auto", "c1", "free"), { kind: "reply", to: "trump" }, open("trump", "c1", "free")],
  ["a click on another member readdresses it", open("putin", "c1", "free"), { kind: "reply", to: "trump" }, open("trump", "c1", "free")],
  ["the picker changes the addressee", open("auto", "c1", "free"), { kind: "address", to: "everyone" }, open("everyone", "c1", "free")],
] as const) {
  test(`dialogueStep: ${name}`, () => assert.deepEqual(dialogueStep(before, event), after));
}
