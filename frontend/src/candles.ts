/** The hall's wall candles: where each hangs, its iron sconce, and the small warm glow it throws like the fire's. */
import type Phaser from "phaser";
import { flicker, hearthFacing } from "./hearth.ts";

/** A candle is set on a wall cell and shines into the room, away from that wall. Decoration only: the server knows nothing of it. */
export interface Candle {
  x: number;
  y: number;
}

/** One in the privy, one beside the front door, and one each on the west and east walls. */
export const CANDLES: readonly Candle[] = [{ x: 19, y: 2 }, { x: 11, y: 13 }, { x: 0, y: 9 }, { x: 19, y: 9 }];

/** Where a candle's light enters the room: the middle of the wall cell's room-side edge, and the way it shines. */
export interface Light {
  x: number;
  y: number;
  dx: number;
  dy: number;
}

export function candleLight(candle: Candle, mapWidth: number, size: number): Light {
  const [dx, dy]: [number, number] = hearthFacing(candle, mapWidth);
  return { x: (candle.x + 0.5 + dx / 2) * size, y: (candle.y + 0.5 + dy / 2) * size, dx, dy };
}

/** Rings of glow around a candle, and how far the outermost reaches in cells; the fire has five rings of 0.62. */
export const GLOW_RINGS = 3;
const RING_REACH = 0.45;

/** The radius in pixels of a glow ring (1 is the innermost, `GLOW_RINGS` the outermost) at calm. */
export function glowRadius(size: number, ring: number): number {
  return ring * size * RING_REACH;
}

/** Each candle burns on its own phase, so the four never flicker as one. */
function phaseOf(index: number): number {
  return index * 2.1;
}

/** The corners of a box seen from a wall: `from` to `to` pixels out from the cell's middle, `half` either side of it. */
function box(centre: { x: number; y: number }, dx: number, dy: number, from: number, to: number, half: number): { x: number; y: number }[] {
  const [px, py]: [number, number] = [-dy, dx];
  const corner = (depth: number, side: number): { x: number; y: number } => ({ x: centre.x + dx * depth + px * side, y: centre.y + dy * depth + py * side });
  return [corner(from, -half), corner(to, -half), corner(to, half), corner(from, half)];
}

/** How far into the wall cell, from its middle, the sconce's dish and candle sit. */
const DISH_DEPTH = 11;

/**
 * Draw every sconce into the static furniture layer: an iron plate on the wall, a brass dish and a pale candle with its wick.
 *
 * @param g Layer for the static furniture.
 * @param mapWidth Hall width in cells, which tells which wall a candle is on.
 * @param size Tile size in pixels.
 */
export function drawSconces(g: Phaser.GameObjects.Graphics, mapWidth: number, size: number): void {
  for (const candle of CANDLES) {
    const { dx, dy }: Light = candleLight(candle, mapWidth, size);
    const centre = { x: (candle.x + 0.5) * size, y: (candle.y + 0.5) * size };
    g.fillStyle(0x1b1713, 0.45).fillPoints(box(centre, dx, dy, 3, 15, 7), true);
    g.fillStyle(0x2b2622).fillPoints(box(centre, dx, dy, 4, 12, 6), true);
    g.fillStyle(0x6d6050).fillPoints(box(centre, dx, dy, 5, 6, 5), true);
    const dish = { x: centre.x + dx * DISH_DEPTH, y: centre.y + dy * DISH_DEPTH };
    g.fillStyle(0x8c6d3a).fillCircle(dish.x, dish.y, 5);
    g.fillStyle(0xb99556).fillCircle(dish.x, dish.y, 3.6);
    g.fillStyle(0xe9dfc0).fillCircle(dish.x, dish.y, 2.4);
    g.fillStyle(0x3a2a1c).fillRect(dish.x - 0.5, dish.y - 0.5, 1, 1);
  }
}

/**
 * Draw each candle's flame and the glow it throws into the room, replacing the last frame's.
 *
 * Same colour and flicker as the fireplace's glow, with fewer, smaller rings.
 *
 * @param g Layer for the candlelight, below the guests and cleared here.
 * @param mapWidth Hall width in cells.
 * @param size Tile size in pixels.
 * @param time Real time in milliseconds, which drives the flicker.
 */
export function drawCandles(g: Phaser.GameObjects.Graphics, mapWidth: number, size: number, time: number): void {
  g.clear();
  CANDLES.forEach((candle: Candle, index: number): void => {
    const strength: number = flicker(time, phaseOf(index));
    const { x, y, dx, dy }: Light = candleLight(candle, mapWidth, size);
    for (let ring: number = GLOW_RINGS; ring > 0; ring -= 1) {
      g.fillStyle(0xf5a347, 0.05 * strength).fillCircle(x, y, glowRadius(size, ring) * strength);
    }
    // The flame stands on the candle, a little inside the wall cell, and leans with the draught.
    const base = { x: (candle.x + 0.5) * size + dx * DISH_DEPTH, y: (candle.y + 0.5) * size + dy * DISH_DEPTH };
    const height: number = 4 * strength;
    const sway: number = 0.8 * Math.sin(time / 130 + phaseOf(index));
    g.fillStyle(0xf08a30).fillPoints([{ x: base.x - 2, y: base.y }, { x: base.x + sway, y: base.y - height - 1 }, { x: base.x + 2, y: base.y }], true);
    g.fillStyle(0xfbd86a).fillPoints([{ x: base.x - 1, y: base.y }, { x: base.x + sway * 0.6, y: base.y - height * 0.6 }, { x: base.x + 1, y: base.y }], true);
  });
}
