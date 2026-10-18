/** The dice game's small motions: each player throws a die across the table, it bounces, tumbles and settles; the winner sparkles. Decoration only. */
import type Phaser from "phaser";
import { auraPhase } from "./aura.ts";
import { cheerSparks, THROW_MS, throwMotion } from "./dartplay.ts";
import type { Actor, WorldEvent, WorldObject } from "./types";

/** One throw, from the hand to the next hand, in milliseconds. */
export const ROLL_MS = 1800;

/** Where a roll is: how far the die has flown (0–1, or -1 once it lies still) and how long it has lain (0 just landed, toward 1 before the next throw). */
export function rollCycle(time: number, phase: number): { flight: number; rest: number } {
  const c: number = ((time + phase * ROLL_MS) % ROLL_MS) / ROLL_MS;
  return c < 0.5 ? { flight: c / 0.5, rest: 0 } : { flight: -1, rest: (c - 0.5) / 0.5 };
}

/** The die's place at `flight` (0–1) between two points: it bounces two and a half times, each bounce lower, and is still at the end. */
export function dieAt(from: { x: number; y: number }, to: { x: number; y: number }, flight: number): { x: number; y: number } {
  const bounce: number = 14 * (1 - flight) * Math.abs(Math.sin(2.5 * Math.PI * flight));
  return { x: from.x + (to.x - from.x) * flight, y: from.y + (to.y - from.y) * flight - bounce };
}

/** How far the die is turned, in radians: it spins in the air and lies at a fixed angle once down. */
export function dieTilt(flight: number): number {
  return flight >= 0 ? flight * 9 : 0.3;
}

/** The pips showing (1–6): a tumbling die flickers through faces, a landed one keeps the face of its throw (`index` counts the throws). */
export function dieFace(flight: number, index: number, phase: number): number {
  return flight >= 0 ? 1 + (Math.floor(flight * 16) + index) % 6 : 1 + (index * 5 + Math.floor(phase * 6)) % 6;
}

/** How far a seated player's sprite is nudged: the dart thrower's wind-up and lunge, slowed to the roll and timed so the lunge ends as the die leaves the hand. */
export function rollLunge(time: number, phase: number, toward: number): { x: number; y: number } {
  return throwMotion(time * THROW_MS / ROLL_MS, phase + 0.25, toward);
}

const PIPS: readonly (readonly [number, number])[][] = [[[0, 0]], [[-2, -2], [2, 2]], [[-2, -2], [0, 0], [2, 2]],
  [[-2, -2], [2, -2], [-2, 2], [2, 2]], [[-2, -2], [2, -2], [0, 0], [-2, 2], [2, 2]],
  [[-2, -2], [2, -2], [-2, 0], [2, 0], [-2, 2], [2, 2]]];

function drawPlayDie(g: Phaser.GameObjects.Graphics, at: { x: number; y: number }, floor: number, pips: number, tilt: number): void {
  const half: number = 4;
  const corner = (dx: number, dy: number): { x: number; y: number } => ({
    x: at.x + dx * Math.cos(tilt) - dy * Math.sin(tilt), y: at.y + dx * Math.sin(tilt) + dy * Math.cos(tilt) });
  const outline = [corner(-half, -half), corner(half, -half), corner(half, half), corner(-half, half)];
  // The shadow stays on the table while the die is up, shrinking as it comes down.
  g.fillStyle(0x33251d, 0.3).fillEllipse(at.x, floor + 3, 7, 3);
  g.fillStyle(0xf3ead2).fillPoints(outline, true);
  g.lineStyle(1, 0x8a7656).strokePoints(outline, true);
  for (const [dx, dy] of PIPS[pips - 1]!) {
    const pip = corner(dx, dy);
    g.fillStyle(0x2b211b).fillCircle(pip.x, pip.y, 1.1);
  }
}

/**
 * Draw the dice in the air over every table with two players seated, and the winner's stars, replacing the last frame's.
 *
 * @param g Layer for the play, above the furniture and cleared here.
 * @param objects The hall's objects: the dice tables are the ones of kind `dice_table` that hold a game with an end.
 * @param actors Everyone in the hall; a table's players are named by its game.
 * @param events The event log, for `dice_won`.
 * @param worldTime Game seconds, to age the winner's cheer.
 * @param size Tile size in pixels.
 * @param time Real time in milliseconds, which drives the throws.
 */
export function drawDicePlay(g: Phaser.GameObjects.Graphics, objects: readonly WorldObject[], actors: readonly Actor[], events: readonly WorldEvent[], worldTime: number, size: number, time: number): void {
  g.clear();
  for (const table of objects) {
    if (table.kind !== "dice_table" || !table.game || table.game.ends_at === null) continue;
    const middle = { x: (table.x + (table.width ?? 1) / 2) * size, y: (table.y + (table.height ?? 1) / 2) * size - 6 };
    for (const id of table.game.players) {
      const player: Actor | undefined = actors.find((item: Actor): boolean => item.id === id);
      if (player === undefined) continue;
      const side: number = Math.sign(player.x + 0.5 - middle.x / size) || 1;
      const phase: number = auraPhase(player.id);
      const { flight } = rollCycle(time, phase);
      const to = { x: middle.x + side * 9, y: middle.y + (side > 0 ? 2 : -3) };
      const hand = { x: (player.x + 0.5) * size - side * 4, y: middle.y - 4 };
      const at = flight >= 0 ? dieAt(hand, to, flight) : to;
      drawPlayDie(g, at, flight >= 0 ? hand.y + (to.y - hand.y) * flight : to.y, dieFace(flight, Math.floor((time + phase * ROLL_MS) / ROLL_MS), phase), dieTilt(flight));
    }
  }
  for (const event of events) {
    if (event.type !== "dice_won" || event.actor_id === null) continue;
    const winner: Actor | undefined = actors.find((item: Actor): boolean => item.id === event.actor_id);
    if (winner === undefined) continue;
    for (const star of cheerSparks(worldTime - event.time, time)) {
      g.fillStyle(0xffe27a, star.alpha).fillCircle((winner.x + 0.5) * size + star.x, (winner.y + 0.5) * size + star.y, 2);
    }
  }
}
