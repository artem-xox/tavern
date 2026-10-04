import type { Actor } from "./types";

/** How one character sprite under /characters is drawn. */
export interface SpriteSheet {
  /** Display size in pixels. */
  size: number;
  /** Vertical offset that rests the figure's feet on its cell. */
  lift: number;
  /** Poses shipped in all four directions; any other pose is drawn as Idle. */
  poses: readonly string[];
}

const DIRECTIONS: readonly string[] = ["north", "south", "east", "west"];
const ALL_POSES: readonly string[] = ["Idle", "Seated", "Darts", "Bathroom", "Drinking", "DrinkingSeated", "TalkingSeated", "TakeBeer", "Walking", "Talking"];

/** Character stills shipped under /characters; an unknown guest looks like Saye. */
const SPRITES: Readonly<Record<string, SpriteSheet>> = {
  edda: { size: 68, lift: -16, poses: ALL_POSES },
  rurik: { size: 68, lift: -16, poses: ALL_POSES },
  toren: { size: 68, lift: -16, poses: ALL_POSES },
  cook: { size: 68, lift: -16, poses: ALL_POSES },
  courier: { size: 68, lift: -16, poses: ALL_POSES },
  visitor: { size: 68, lift: -16, poses: ALL_POSES },
};

/** Every still to load: one texture per sprite, shipped pose and direction. */
export function stills(): { key: string; url: string }[] {
  return Object.entries(SPRITES).flatMap(([sprite, sheet]: [string, SpriteSheet]) => sheet.poses.flatMap((pose: string) =>
    DIRECTIONS.map((direction: string) => ({ key: `${sprite}-${pose}-${direction}`, url: `/characters/${sprite}/${pose}/rotations/${direction}.png` }))));
}

/** The guest's own sprite when it ships, otherwise the generic visitor. */
export function spriteOf(actor: Actor): { name: string; sheet: SpriteSheet } {
  const name: string = Object.hasOwn(SPRITES, actor.sprite) ? actor.sprite : "visitor";
  return { name, sheet: SPRITES[name]! };
}

/** The pose to draw: the wanted one when the sprite ships it, otherwise Idle rather than a missing image. */
export function shippedPose(sheet: SpriteSheet, wanted: string): string {
  return sheet.poses.includes(wanted) ? wanted : "Idle";
}
