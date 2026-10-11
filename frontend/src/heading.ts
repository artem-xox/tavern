import type { Facing } from "./types";

/**
 * The eight ways a figure can face, east first and clockwise on the screen (y grows down), one 45-degree sector each.
 * The same sectors as `COMPASS` in `backend/tavern/body/expression.py`, so the client turns a guest as the server does.
 */
const COMPASS: readonly Facing[] = ["east", "south-east", "south", "south-west", "west", "north-west", "north", "north-east"];

/** The heading of a vector in screen cells, or null when it has no length. */
export function headingOf(dx: number, dy: number): Facing | null {
  if (dx === 0 && dy === 0) return null;
  const sector: number = Math.round(Math.atan2(dy, dx) / (Math.PI / 4));
  return COMPASS[((sector % 8) + 8) % 8]!;
}

/** A thing with a place on the map: one cell unless it has a size (`width` and `height` in cells). */
export interface Footprint {
  x: number;
  y: number;
  width?: number;
  height?: number;
}

/**
 * The heading from the middle of a visitor's cell to the nearest point of an object, or null when they stand on it.
 * The nearest point, not the middle: beside any cell of a wide bar a guest faces the bar, not its far end.
 */
export function headingToObject(from: { x: number; y: number }, target: Footprint): Facing | null {
  const clamp = (value: number, low: number, high: number): number => Math.min(Math.max(value, low), high);
  const cx: number = from.x + 0.5;
  const cy: number = from.y + 0.5;
  return headingOf(clamp(cx, target.x, target.x + (target.width ?? 1)) - cx, clamp(cy, target.y, target.y + (target.height ?? 1)) - cy);
}
