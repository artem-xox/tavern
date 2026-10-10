/** A figure's fight and wound effects on screen: the cudgel in hand, the stars, and the per-frame motion and tint. */
import Phaser from "phaser";
import { blowFlash, blowShake, cudgelHand, fightMotion, healthTint, lastBlowOn, limp, showsCudgel, starsOrbit } from "./fightview";
import type { Actor, Facing, Fight } from "./types";

/** A cudgel's pixels (`.` clear, `1` wood, `2` grip, `3` shadow), drawn at twice their size in a hand. */
const CUDGEL: readonly string[] = ["..11..", ".1111.", ".1131.", ".1131.", ".1131.", "..11..", "..22..", "..22..", "..22.."];
const CUDGEL_PALETTE: Readonly<Record<string, string>> = { "1": "#8a5a2c", "2": "#4a2f19", "3": "#6b4220" };

/** What a snapshot says of a figure's fight and wounds, with the objects that show it. */
export interface Wounds {
  cudgel: Phaser.GameObjects.Image;
  stars: Phaser.GameObjects.Text[];
  /** Where the sprite rests on its cell, before any motion. */
  baseY: number;
  fighting: boolean;
  phase: 0 | 1;
  lying: boolean;
  limping: boolean;
  starry: boolean;
  tint: number;
  lastBlow: number | null;
  worldTime: number;
}

/** Make the cudgel's texture once; every figure's cudgel shares it. */
export function makeCudgelTexture(scene: Phaser.Scene): void {
  scene.textures.generate("cudgel", { data: [...CUDGEL], pixelWidth: 2, palette: CUDGEL_PALETTE as unknown as Phaser.Types.Create.Palette });
  scene.textures.get("cudgel").setFilter(Phaser.Textures.FilterMode.NEAREST);
}

/** A figure's cudgel and three stars, hidden until a snapshot calls for them. */
export function createWounds(scene: Phaser.Scene, baseY: number): Wounds {
  const cudgel: Phaser.GameObjects.Image = scene.add.image(0, 0, "cudgel").setVisible(false);
  const stars: Phaser.GameObjects.Text[] = [0, 1, 2].map((): Phaser.GameObjects.Text =>
    scene.add.text(0, -40, "★", { fontFamily: "system-ui", fontSize: "11px", color: "#ffd84a", stroke: "#3a2a10", strokeThickness: 2 }).setOrigin(0.5).setVisible(false));
  return { cudgel, stars, baseY, fighting: false, phase: 0, lying: false, limping: false, starry: false, tint: 0xffffff, lastBlow: null, worldTime: 0 };
}

/**
 * Read a fight and a wound off the snapshot: the stance, the tint, the cudgel in hand and the stars. `wanted` is the
 * pose asked for and `pose` the one drawn, which differs where the sprite has no art for it yet.
 */
export function readWounds(wounds: Wounds, container: Phaser.GameObjects.Container, actor: Actor, fights: readonly Fight[],
  time: number, wanted: string, pose: string, direction: string): void {
  const fight: Fight | undefined = fights.find((item: Fight): boolean => item.outcome === null && (item.a === actor.id || item.b === actor.id));
  wounds.fighting = wanted === "Fighting";
  wounds.phase = fight && fight.b === actor.id ? 1 : 0;
  // A lying figure the sprite has no art for is the sleeping pose turned on its side.
  wounds.lying = wanted === "KnockedOut" && pose !== "KnockedOut";
  wounds.limping = actor.status === "walking" && actor.health < 70;
  wounds.starry = actor.condition === "groggy" || actor.condition === "staggered";
  wounds.tint = healthTint(actor.health);
  wounds.lastBlow = lastBlowOn(fights, actor.id);
  wounds.worldTime = time;
  const holds: boolean = (actor.inventory.cudgel ?? 0) > 0 && showsCudgel(wanted);
  wounds.cudgel.setVisible(holds);
  if (!holds) return;
  const hand = cudgelHand(direction as Facing, wounds.fighting);
  wounds.cudgel.setPosition(hand.x, hand.y + wounds.baseY + 20).setAngle(hand.angle);
  if (hand.behind) container.sendToBack(wounds.cudgel); else container.bringToTop(wounds.cudgel);
}

/** Per frame: the sway, a fighter's lunge, the shake and red flash of a blow, a limp, the stars and the tint. */
export function animateWounds(wounds: Wounds, sprite: Phaser.GameObjects.Image, sway: number, time: number, direction: string): void {
  let angle: number = sway;
  let x: number = 0;
  let y: number = wounds.baseY;
  if (wounds.fighting) {
    const motion = fightMotion(time, direction as Facing, wounds.phase);
    x += motion.x; y += motion.y; angle += motion.angle;
  }
  const since: number = wounds.lastBlow === null ? -1 : wounds.worldTime - wounds.lastBlow;
  const shake = blowShake(since, time);
  x += shake.x; angle += shake.angle;
  if (wounds.limping) y += limp(time);
  if (wounds.lying) { angle = 90; y += 14; }
  sprite.setAngle(angle).setPosition(x, y);
  if (blowFlash(since) > 0) sprite.setTint(0xff5a4a);
  else if (wounds.tint === 0xffffff) sprite.clearTint();
  else sprite.setTint(wounds.tint);
  starsOrbit(time).forEach((offset: { x: number; y: number }, index: number): void => {
    wounds.stars[index]!.setVisible(wounds.starry).setPosition(offset.x, -42 + offset.y);
  });
}
