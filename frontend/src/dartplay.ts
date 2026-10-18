/** The dart game's small motions: the thrower's lunge, the dart in flight, the sparks of a hit and the winner's cheer. Decoration only. */
import type Phaser from "phaser";
import { auraPhase } from "./aura.ts";
import type { Actor, WorldEvent, WorldObject } from "./types";

/** One throw, from wind-up to the next wind-up, in milliseconds. */
export const THROW_MS = 1400;
/** How long a winner sparkles after the match, in game seconds. */
export const CHEER_SECONDS = 2.5;

/** Where a throw is: how far the dart has flown (0–1, or -1 once it sticks in the board) and how fresh the hit is (1 at impact, fading to 0). */
export function throwCycle(time: number, phase: number): { flight: number; hit: number } {
  const c: number = ((time + phase * THROW_MS) % THROW_MS) / THROW_MS;
  return c < 0.4 ? { flight: c / 0.4, hit: 0 } : { flight: -1, hit: 1 - (c - 0.4) / 0.6 };
}

/** Where a thrower's hand is, from their cell: a little toward the board's side and 34 px above the cell's middle, at four fifths of a 60 px figure (feet 14 px below it). */
export function handOf(cell: { x: number; y: number }, size: number): { x: number; y: number } {
  return { x: (cell.x + 0.5) * size - 6, y: (cell.y + 0.5) * size - 34 };
}

/** The dart's place at `flight` (0–1) from the hand to the board, lifted in an arc that is highest midway. */
export function dartAt(from: { x: number; y: number }, to: { x: number; y: number }, flight: number): { x: number; y: number } {
  return { x: from.x + (to.x - from.x) * flight, y: from.y + (to.y - from.y) * flight - Math.sin(Math.PI * flight) * 8 };
}

/** How far a thrower's sprite is nudged: back to wind up, then toward the board (`toward` is -1 west, 1 east) as the dart leaves. */
export function throwMotion(time: number, phase: number, toward: number): { x: number; y: number } {
  const c: number = ((time + phase * THROW_MS) % THROW_MS) / THROW_MS;
  if (c < 0.25) return { x: -toward * Math.sin(Math.PI * c / 0.25) * 1.4, y: 0 };
  if (c < 0.45) {
    const lunge: number = Math.sin(Math.PI * (c - 0.25) / 0.2);
    return { x: toward * lunge * 2.4, y: -lunge * 1.2 };
  }
  return { x: 0, y: 0 };
}

/** Sparks flung from the bullseye by a fresh hit (`hit` 1 at impact): six that fly outward and fade, none once the burst is over. */
export function hitSparks(hit: number): { x: number; y: number; alpha: number }[] {
  if (hit < 0.6) return [];
  const reach: number = (1 - hit) * 28 + 2;
  return Array.from({ length: 6 }, (_: unknown, index: number): { x: number; y: number; alpha: number } => {
    const angle: number = index * Math.PI / 3 + 0.4;
    return { x: Math.cos(angle) * reach, y: Math.sin(angle) * reach, alpha: (hit - 0.6) / 0.4 };
  });
}

/** Stars that rise round a winner `since` game seconds after the match (offsets from their middle), none before or after the cheer. */
export function cheerSparks(since: number, time: number): { x: number; y: number; alpha: number }[] {
  if (since < 0 || since >= CHEER_SECONDS) return [];
  return Array.from({ length: 5 }, (_: unknown, index: number): { x: number; y: number; alpha: number } => ({
    x: (index - 2) * 7 + Math.sin(time / 200 + index) * 2,
    y: -36 - since * 9 - (index % 2) * 5,
    alpha: 1 - since / CHEER_SECONDS,
  }));
}

/**
 * Draw the darts in the air, the sparks where they land and the winner's stars, replacing the last frame's.
 *
 * @param g Layer for the play, above the furniture and cleared here.
 * @param objects The hall's objects: the dart boards are the ones of kind `darts`.
 * @param actors Everyone in the hall; those throwing at a board while interacting are the throwers.
 * @param events The event log, for `darts_won`.
 * @param worldTime Game seconds, to age the winner's cheer.
 * @param size Tile size in pixels.
 * @param time Real time in milliseconds, which drives the throws.
 */
export function drawDartPlay(g: Phaser.GameObjects.Graphics, objects: readonly WorldObject[], actors: readonly Actor[], events: readonly WorldEvent[], worldTime: number, size: number, time: number): void {
  g.clear();
  for (const actor of actors) {
    const board: WorldObject | undefined = actor.action?.verb === "play_darts" && actor.status === "interacting" ? objects.find((item: WorldObject): boolean => item.id === actor.action?.target_id) : undefined;
    if (board === undefined) continue;
    const phase: number = auraPhase(actor.id);
    const aim = { x: (board.x + 0.5) * size, y: (board.y + 0.5) * size };
    const hand = handOf(actor, size);
    const { flight, hit } = throwCycle(time, phase);
    const at = flight >= 0 ? dartAt(hand, aim, flight) : aim;
    // The dart's tail trails behind it in flight; once it has landed, only its flights show above the bullseye.
    if (flight >= 0) g.lineStyle(2, 0xe5c178).lineBetween(at.x, at.y, at.x + 6, at.y - 1).fillStyle(0xf5ecd0).fillCircle(at.x, at.y, 1.5);
    g.lineStyle(1, 0xf5e3b6, hit * 0.8).strokeCircle(aim.x, aim.y, 5 + (1 - hit) * 12);
    for (const spark of hitSparks(hit)) g.fillStyle(0xffe0a3, spark.alpha).fillCircle(aim.x + spark.x, aim.y + spark.y, 1.4);
  }
  for (const event of events) {
    if (event.type !== "darts_won" || event.actor_id === null) continue;
    const winner: Actor | undefined = actors.find((item: Actor): boolean => item.id === event.actor_id);
    if (winner === undefined) continue;
    for (const star of cheerSparks(worldTime - event.time, time)) {
      g.fillStyle(0xffe27a, star.alpha).fillCircle((winner.x + 0.5) * size + star.x, (winner.y + 0.5) * size + star.y, 2);
    }
  }
}
