import { STAND_INS } from "./fightview.ts";
import type { Actor, CharacterCatalog } from "./types";

/** How one catalog character's sprites are drawn. */
export interface SpriteSheet {
  size: number;
  lift: number;
  poses: readonly string[];
}

export type SpriteRegistry = Readonly<Record<string, SpriteSheet>>;

const DIRECTIONS: readonly string[] = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"];
const LEGACY_SPRITES: Readonly<Record<string, string>> = { cook: "brida", courier: "calder", visitor: "saye", bartender: "hob" };

/** Build the rendering registry from the server's public character catalog. */
export function spriteSheets(catalog: CharacterCatalog): SpriteRegistry {
  return Object.fromEntries(catalog.characters.map((character) => [character.sprite, character.visuals]));
}

/** Every still to load: one texture per sprite, shipped pose and direction. */
export function stills(sprites: SpriteRegistry): { key: string; url: string }[] {
  return Object.entries(sprites).flatMap(([sprite, sheet]) => sheet.poses.flatMap((pose) =>
    DIRECTIONS.map((direction) => ({ key: `${sprite}-${pose}-${direction}`, url: `/characters/${sprite}/${pose}/rotations/${direction}.png` }))));
}

/** Find catalog art, translating only sprite names persisted by earlier saves. */
export function spriteOf(actor: Actor, sprites: SpriteRegistry): { name: string; sheet: SpriteSheet } {
  const name: string = LEGACY_SPRITES[actor.sprite] ?? actor.sprite;
  const sheet: SpriteSheet | undefined = sprites[name];
  if (!sheet) throw new Error(`No catalog art for character ${actor.sprite}`);
  return { name, sheet };
}

/**
 * The pose to draw: the wanted one when the sprite ships it, or an old-save fallback.
 */
export function shippedPose(sheet: SpriteSheet, wanted: string): string {
  if (sheet.poses.includes(wanted)) return wanted;
  const standIn: string | undefined = (STAND_INS[wanted] ?? []).find((pose: string): boolean => sheet.poses.includes(pose));
  if (standIn) return standIn;
  return wanted.endsWith("Seated") && sheet.poses.includes("Seated") ? "Seated" : "Idle";
}
