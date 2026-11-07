/** What a pointer position means on the map: the cell, the visitor or object under it, and the words for hovering. */
import type { Cell, WorldObject } from "./types";

/** How far from a visitor's drawn position a pointer still picks them, in tiles. */
const REACH = 0.65;

export interface PickMap {
  width: number;
  height: number;
  tile_size: number;
}

/** The parts of an object that picking and hover text read. */
export type PickObject = Pick<WorldObject, "id" | "kind" | "name" | "x" | "y" | "width" | "height" | "stock" | "reserved_by" | "appeal" | "comforts" | "game">;

/** The cell under a pointer, or null when it is outside the map. */
export function cellAt(x: number, y: number, map: PickMap): Cell | null {
  const cx: number = Math.floor(x / map.tile_size);
  const cy: number = Math.floor(y / map.tile_size);
  if (cx < 0 || cy < 0 || cx >= map.width || cy >= map.height) return null;
  return [cx, cy];
}

/** The visitor drawn within reach of the pointer (the nearest when two are), or null. */
export function visitorAt(x: number, y: number, positions: ReadonlyMap<string, { x: number; y: number }>, tileSize: number): string | null {
  let found: string | null = null;
  let best: number = tileSize * REACH;
  for (const [id, at] of positions) {
    const distance: number = Math.hypot(x - at.x, y - at.y);
    if (distance <= best) { found = id; best = distance; }
  }
  return found;
}

/** The object whose footprint covers the cell, or null. */
export function objectAt<T extends PickObject>(cell: Cell, objects: readonly T[]): T | null {
  const [x, y] = cell;
  return objects.find((item: T): boolean => x >= item.x && x < item.x + (item.width ?? 1) && y >= item.y && y < item.y + (item.height ?? 1)) ?? null;
}

/** What is under the pointer, as plain data. */
export interface HoverView {
  cell: Cell;
  object: PickObject | null;
  /** The name of the visitor whose favourite seat the object is, if any. */
  owner: string | null;
  /** The names of the players at a game table, in order. */
  playerNames: readonly string[];
  /** A visitor showing an emote within reach, with the word for it; null when none. */
  emoted: { name: string; word: string } | null;
  editing: boolean;
}

/** The line shown while hovering. */
export function hoverText(view: HoverView): string {
  if (view.emoted) return `${view.emoted.name} · ${view.emoted.word}`;
  const { object, cell, owner } = view;
  if (!object) return `${view.editing ? "Click to toggle obstacle" : "Click a visitor to inspect"} · cell ${cell[0]}, ${cell[1]}`;
  const stock: string = object.kind === "tap" ? ` · ${object.stock ?? 0} left` : "";
  const players: string = object.game ? ` · ${view.playerNames.join(" and ")} playing` : "";
  const appeal: string = object.appeal !== undefined ? ` · appeal ${object.appeal.toFixed(2)}${object.comforts?.length ? ` (${object.comforts.join(", ")})` : ""}` : "";
  return `${object.name} · ${object.reserved_by ? "reserved" : "available"}${owner ? ` · ${owner}'s seat` : ""}${stock}${players}${appeal} · cell ${cell[0]}, ${cell[1]}`;
}
