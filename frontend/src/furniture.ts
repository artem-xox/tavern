/** Drawing of the hall's furniture and fittings, one function per object kind. */
import Phaser from "phaser";
import { flicker } from "./hearth.ts";
import { diceInPlay } from "./mapview.ts";
import { footlights, performing } from "./stage.ts";
import type { Actor, WorldObject } from "./types";

/**
 * The entrance: a plank door in a timber frame, as tall as the wall stones beside it (`floor.ts`'s `drawWall`
 * draws a stone from 2 px below its cell's top to 3 px above its bottom).
 */
export function drawDoor(g: Phaser.GameObjects.Graphics, door: WorldObject, size: number): void {
  const width: number = 1.6 * size;
  const left: number = (door.x + 0.5) * size - width / 2;
  const top: number = door.y * size + 2;
  const height: number = size - 5;
  const planks: number = 4;
  const plank: number = width / planks;
  // Timber frame, a lintel in lighter wood, and a stone threshold.
  g.fillStyle(0x2a2018).fillRoundedRect(left - 3, top, width + 6, height, 3);
  g.fillStyle(0x4a3827).fillRect(left - 3, top, width + 6, 3);
  g.fillStyle(0x8d8378).fillRect(left, top + height - 3, width, 3);
  // Planks, each its own shade, with a dark seam between and a pale top edge.
  for (let index: number = 0; index < planks; index += 1) {
    g.fillStyle(index % 2 ? 0x5c3f2c : 0x6e4e37).fillRect(left + index * plank, top + 3, plank, height - 6);
    g.fillStyle(0x2a2018).fillRect(left + index * plank, top + 3, 1, height - 6);
    g.fillStyle(0xa27a52, 0.7).fillRect(left + index * plank + 1, top + 3, plank - 1, 1);
  }
  // Two iron straps with a rivet on each plank, and a brass ring on the latch side.
  for (const strap of [top + 7, top + height - 11]) {
    g.fillStyle(0x3b3a38).fillRect(left, strap, width, 3);
    for (let index: number = 0; index < planks; index += 1) g.fillStyle(0x9a9588).fillRect(left + index * plank + plank / 2 - 1, strap + 1, 2, 1);
  }
  g.fillStyle(0x1b130e).fillCircle(left + width - 8, top + height / 2 + 1, 4);
  g.fillStyle(0xe2c27a).fillCircle(left + width - 8, top + height / 2 + 1, 3);
  g.fillStyle(0x6e4e37).fillCircle(left + width - 8, top + height / 2 + 1, 1.2);
}

export function drawWindow(g: Phaser.GameObjects.Graphics, pane: WorldObject, size: number): void {
  const x: number = pane.x * size;
  const y: number = pane.y * size;
  g.fillStyle(0x403e34).fillRoundedRect(x + 5, y + 3, 22, 26, 2);
  g.fillStyle(0x88a39c).fillRect(x + 9, y + 6, 14, 19);
  g.lineStyle(2, 0xd3b584).lineBetween(x + 16, y + 6, x + 16, y + 25);
  g.lineBetween(x + 9, y + 15, x + 23, y + 15);
  g.fillStyle(0xc7a272).fillRect(x + 6, y + 26, 23, 4);
}

export function drawTap(g: Phaser.GameObjects.Graphics, x: number, y: number): void {
  g.fillStyle(0x3f3528).fillRoundedRect(x - 13, y - 14, 26, 29, 5);
  g.fillStyle(0xb8803c).fillRoundedRect(x - 10, y - 12, 20, 24, 4);
  g.lineStyle(3, 0x674b32).lineBetween(x - 9, y - 7, x + 9, y - 7);
  g.lineBetween(x - 9, y + 7, x + 9, y + 7);
  g.fillStyle(0xe8c873).fillRect(x - 3, y - 3, 6, 14);
  g.fillRect(x - 2, y + 5, 9, 4);
}

/** The privy: a squat tub in the chairs' woods, standing in the middle of the stone floor: two tones of plank, dark bands, a pale rim and a lug on each side. */
export function drawToilet(g: Phaser.GameObjects.Graphics, x: number, y: number): void {
  g.fillStyle(0x4d3425).fillRoundedRect(x - 13, y - 8, 26, 24, 6);
  g.fillStyle(0xa2774d).fillRoundedRect(x - 11, y - 5, 22, 19, 4);
  g.fillStyle(0xc09867).fillRoundedRect(x - 9, y - 3, 5, 15, 2);
  g.fillStyle(0x905b3d).fillRoundedRect(x + 4, y - 3, 5, 15, 2);
  for (const band of [y + 2, y + 9]) g.lineStyle(3, 0x4d3425).lineBetween(x - 11, band, x + 11, band);
  g.fillStyle(0x4d3425).fillRoundedRect(x - 16, y - 2, 4, 7, 1).fillRoundedRect(x + 12, y - 2, 4, 7, 1);
  g.fillStyle(0xc09867).fillEllipse(x, y - 7, 25, 11);
  g.fillStyle(0x33251d).fillEllipse(x, y - 7, 17, 6);
}

export function drawChair(g: Phaser.GameObjects.Graphics, x: number, y: number, facing: WorldObject["facing"]): void {
  g.fillStyle(0x4d3425).fillRoundedRect(x - 11, y - 12, 22, 25, 3);
  g.fillStyle(0xa2774d).fillRoundedRect(x - 8, y - 3, 16, 13, 2);
  g.fillStyle(0xc09867);
  if (facing === "east") g.fillRoundedRect(x - 12, y - 10, 7, 20, 2);
  else if (facing === "west") g.fillRoundedRect(x + 5, y - 10, 7, 20, 2);
  else if (facing === "north") g.fillRoundedRect(x - 10, y + 5, 20, 7, 2);
  else g.fillRoundedRect(x - 10, y - 12, 20, 7, 2);
  g.fillStyle(0x905b3d).fillRoundedRect(x - 5, y - 4, 10, 11, 2);
}

export function drawBar(g: Phaser.GameObjects.Graphics, object: WorldObject, size: number): void {
  const x: number = object.x * size;
  const y: number = object.y * size;
  const width: number = (object.width ?? 1) * size;
  g.fillStyle(0x3e2b20).fillRoundedRect(x - 2, y + 4, width + 4, size, 4);
  g.fillStyle(0xb78650).fillRoundedRect(x - 3, y - 2, width + 6, size - 5, 4);
  g.fillStyle(0x6f4930).fillRoundedRect(x + 2, y + 2, width - 4, size - 13, 2);
  g.lineStyle(2, 0xe3bd7f).lineBetween(x + 2, y + 2, x + width - 2, y + 2);
  g.lineStyle(3, 0xcfab67).lineBetween(x + 5, y + size + 3, x + width - 5, y + size + 3);
  for (let i: number = 0; i < 3; i += 1) {
    g.fillStyle([0x678167, 0xb87946, 0x71868a][i]!).fillRoundedRect(x + 12 + i * 12, y + 7, 6, 10, 2);
    g.fillRect(x + 14 + i * 12, y + 3, 2, 6);
  }
  drawMug(g, x + width - 19, y + 10);
}

/** How far a table's top stands above the floor in the picture, so a guest asleep on it has something to rest on. */
const TABLE_LIFT: number = 6;

/** The table: its shadow on the floor, the plank side that gives it height, then the raised top with rim, planks and inlay. */
function drawTableTop(g: Phaser.GameObjects.Graphics, object: WorldObject, size: number): void {
  const x: number = object.x * size;
  const y: number = object.y * size - TABLE_LIFT;
  const width: number = (object.width ?? 1) * size;
  const height: number = (object.height ?? 1) * size;
  g.fillStyle(0x33251d, 0.5).fillRoundedRect(x - 2, y + TABLE_LIFT + 5, width + 4, height, 8);
  // The side below the top, darkest at the bottom edge, with a shadowed band under the rim.
  g.fillStyle(0x3a281d).fillRoundedRect(x - 1, y + 4, width + 2, height + TABLE_LIFT, 6);
  g.fillStyle(0x6a4631).fillRoundedRect(x + 1, y + height - 2, width - 2, TABLE_LIFT + 1, 3);
  g.fillStyle(0x2c1d14, 0.55).fillRect(x + 2, y + height + 1, width - 4, 2);
  g.fillStyle(0x58392a).fillRoundedRect(x - 2, y - 2, width + 4, height + 4, 6);
  g.fillStyle(0xb48959).fillRoundedRect(x + 1, y + 1, width - 2, height - 2, 5);
  for (let row: number = 12; row < height; row += 14) {
    g.lineStyle(1, 0x785037, 0.5).lineBetween(x + 4, y + row, x + width - 4, y + row);
  }
  g.lineStyle(1, 0xe6c187, 0.6).strokeRoundedRect(x + 3, y + 3, width - 6, height - 6, 3);
}

export function drawTable(g: Phaser.GameObjects.Graphics, object: WorldObject, size: number): void {
  drawTableTop(g, object, size);
}

/** The dice table: the bare top with a pair of ivory dice mid-throw and no candle or mugs. */
export function drawDiceTable(g: Phaser.GameObjects.Graphics, object: WorldObject, size: number): void {
  drawTableTop(g, object, size);
  const cx: number = (object.x + (object.width ?? 1) / 2) * size;
  const cy: number = (object.y + (object.height ?? 1) / 2) * size - TABLE_LIFT;
  // While a game is on, the players' own dice are thrown across the table (`diceplay.ts`); the resting pair would be a third and fourth.
  if (diceInPlay(object)) return;
  drawDie(g, cx - 5, cy + 2, 3, -0.25);
  drawDie(g, cx + 6, cy - 3, 5, 0.35);
}

/** One die, turned by `tilt` radians, showing `pips` pips (1–6). */
function drawDie(g: Phaser.GameObjects.Graphics, x: number, y: number, pips: number, tilt: number): void {
  const side: number = 8;
  const corner = (dx: number, dy: number): { x: number; y: number } => ({
    x: x + dx * Math.cos(tilt) - dy * Math.sin(tilt), y: y + dx * Math.sin(tilt) + dy * Math.cos(tilt) });
  g.fillStyle(0x33251d, 0.4).fillRoundedRect(x - side / 2 + 1, y - side / 2 + 3, side, side, 2);
  const half: number = side / 2;
  g.fillStyle(0xf3ead2).fillPoints([corner(-half, -half), corner(half, -half), corner(half, half), corner(-half, half)], true);
  g.lineStyle(1, 0x8a7656).strokePoints([corner(-half, -half), corner(half, -half), corner(half, half), corner(-half, half)], true);
  const spots: [number, number][][] = [[[0, 0]], [[-2, -2], [2, 2]], [[-2, -2], [0, 0], [2, 2]],
    [[-2, -2], [2, -2], [-2, 2], [2, 2]], [[-2, -2], [2, -2], [0, 0], [-2, 2], [2, 2]],
    [[-2, -2], [2, -2], [-2, 0], [2, 0], [-2, 2], [2, 2]]];
  for (const [dx, dy] of spots[pips - 1]!) {
    const pip = corner(dx, dy);
    g.fillStyle(0x2b211b).fillCircle(pip.x, pip.y, 1.1);
  }
}

/** Lay a rug under every table and its chairs, kept clear of the walls. */
export function drawRugs(floor: Phaser.GameObjects.Graphics, objects: WorldObject[], size: number): void {
  objects.filter((object: WorldObject): boolean => object.kind === "table" || object.kind === "dice_table").forEach((table: WorldObject): void => {
    // Yellow for every ordinary table; card-table green for the dice, so the game's corner reads at a glance.
    const [fill, trim] = table.kind === "dice_table" ? [0x2f5a3e, 0x9cc79a] : [0x7b5b30, 0xd9b26b];
    const x: number = (table.x - 1.2) * size;
    const y: number = (table.y - 0.3) * size;
    const width: number = ((table.width ?? 1) + 2.4) * size;
    const height: number = ((table.height ?? 1) + 0.6) * size;
    floor.fillStyle(0x2b211b, 0.35).fillRoundedRect(x - 2, y + 3, width + 4, height, 7);
    floor.fillStyle(fill).fillRoundedRect(x, y, width, height, 6);
    floor.lineStyle(2, trim, 0.55).strokeRoundedRect(x + 4, y + 4, width - 8, height - 8, 4);
    for (let col: number = 0; col < 6; col += 1) {
      const cx: number = x + (col + 0.5) * width / 6;
      floor.lineStyle(1, trim, 0.2).strokePoints([{ x: cx, y: y + height / 2 - 6 }, { x: cx + 6, y: y + height / 2 }, { x: cx, y: y + height / 2 + 6 }, { x: cx - 6, y: y + height / 2 }], true);
    }
  });
}

function drawMug(g: Phaser.GameObjects.Graphics, x: number, y: number): void {
  g.lineStyle(2, 0xe6d5ad).strokeRoundedRect(x + 1, y - 2, 7, 7, 2);
  g.fillStyle(0xcea15e).fillRoundedRect(x - 4, y - 5, 8, 12, 2);
  g.fillStyle(0xf5e3b6).fillEllipse(x, y - 4, 9, 4);
}

export function drawDarts(g: Phaser.GameObjects.Graphics, x: number, y: number): void {
  // The panel fills its cell, so two boards on neighbouring cells read as one backboard two cells wide.
  g.fillStyle(0x3b2b22).fillRect(x - 15, y - 16, 30, 32);
  g.fillStyle(0xb69769).fillCircle(x, y, 13);
  g.fillStyle(0x243a31).fillCircle(x, y, 11);
  g.lineStyle(2, 0xbb6954).strokeCircle(x, y, 8);
  for (let i: number = 0; i < 12; i += 1) {
    const angle: number = i * Math.PI / 6;
    g.lineStyle(1, 0xe4d3aa, 0.6).lineBetween(x + Math.cos(angle) * 3, y + Math.sin(angle) * 3, x + Math.cos(angle) * 11, y + Math.sin(angle) * 11);
  }
  g.fillStyle(0xce7358).fillCircle(x, y, 3);
  g.lineStyle(2, 0xe5c178).lineBetween(x + 1, y - 3, x + 8, y - 10);
}

/** The way a stage's front faces the room, as a step of one cell. */
const FRONT: Record<NonNullable<WorldObject["facing"]>, [number, number]> = { west: [-1, 0], east: [1, 0], north: [0, -1], south: [0, 1] };
/** Pixels between two pennants of the bunting along the stage's back edge. */
const PENNANT_GAP = 7;

/**
 * A speaker's stage, as big as its object: a raised plank platform with boards along its front edge, a dark trim and a
 * step on the room's side at the speaker's spot, a lectern before the spot, bunting along the back, and brass dishes
 * for the two footlights (`drawFootlights` lights them).
 */
export function drawStage(g: Phaser.GameObjects.Graphics, stage: WorldObject, size: number): void {
  const left: number = stage.x * size;
  const top: number = stage.y * size;
  const width: number = (stage.width ?? 1) * size;
  const height: number = (stage.height ?? 1) * size;
  const [dx, dy]: [number, number] = FRONT[stage.facing ?? "west"];
  // The platform's side shows below its top, so it reads as raised.
  g.fillStyle(0x3a2a1c).fillRoundedRect(left + 1, top + 4, width - 2, height - 3, 3);
  g.fillStyle(0x8a6a44).fillRoundedRect(left + 1, top + 1, width - 2, height - 4, 3);
  const across: boolean = dx !== 0;
  for (let at: number = 8; at < (across ? width : height) - 2; at += 8) {
    if (across) g.lineStyle(1, 0x5b4129, 0.7).lineBetween(left + at, top + 3, left + at, top + height - 5);
    else g.lineStyle(1, 0x5b4129, 0.7).lineBetween(left + 3, top + at, left + width - 3, top + at);
  }
  const [spotX, spotY]: [number, number] = (stage.interaction_spots[0] ?? [stage.x, stage.y]) as [number, number];
  const cx: number = (spotX + 0.5) * size;
  const cy: number = (spotY + 0.5) * size;
  // The front trim, then the step just outside the front edge and the lectern just inside it, both at the spot.
  const frontX: number = dx < 0 ? left + 1 : dx > 0 ? left + width - 5 : left + 1;
  const frontY: number = dy < 0 ? top + 1 : dy > 0 ? top + height - 7 : top + 1;
  g.fillStyle(0x5a3f27).fillRect(frontX, frontY, across ? 4 : width - 2, across ? height - 4 : 4);
  const edge = { x: cx + dx * size / 2, y: cy + dy * size / 2 };
  g.fillStyle(0x6b4f33).fillRect(edge.x + dx * 3 - (across ? 3 : 7), edge.y + dy * 3 - (across ? 7 : 3), across ? 6 : 14, across ? 14 : 6);
  const lectern = { x: cx + dx * 9, y: cy + dy * 9 };
  g.fillStyle(0x4a3220).fillRect(lectern.x - (across ? 3 : 6), lectern.y - (across ? 6 : 3), across ? 7 : 12, across ? 12 : 7);
  g.fillStyle(0x7a5636).fillRect(lectern.x - (across ? 3 : 6), lectern.y - (across ? 6 : 3), across ? 7 : 12, 3);
  // Bunting along the back edge, the pennants pointing into the room, red and gold in turn.
  const backX: number = dx < 0 ? left + width - 3 : dx > 0 ? left + 3 : left + 3;
  const backY: number = dy < 0 ? top + height - 6 : dy > 0 ? top + 3 : top + 3;
  const length: number = across ? height - 6 : width - 6;
  for (let at: number = 3, index: number = 0; at + 5 <= length; at += PENNANT_GAP, index += 1) {
    const base = across ? { x: backX, y: top + at } : { x: left + at, y: backY };
    const tip = { x: base.x + dx * 5 + (across ? 0 : 2.5), y: base.y + dy * 5 + (across ? 2.5 : 0) };
    const end = across ? { x: base.x, y: base.y + 5 } : { x: base.x + 5, y: base.y };
    g.fillStyle(index % 2 === 0 ? 0xb5483a : 0xe5c178).fillTriangle(base.x, base.y, end.x, end.y, tip.x, tip.y);
  }
  for (const light of footlights(stage, size)) g.fillStyle(0xb08a3e).fillCircle(light.x, light.y + 2, 3);
}

/**
 * The stages' footlights, redrawn every frame like the candles: a small flame on each brass dish that flares, with a
 * wide warm glow on the boards, while a number is on (`stage.performing`).
 *
 * @param g Layer for the footlights.
 * @param objects The hall's objects; only stages have footlights.
 * @param actors The hall's visitors, who tell whether anyone is performing.
 * @param size Tile size in pixels.
 * @param time Milliseconds since the scene began, for the flicker.
 */
export function drawFootlights(g: Phaser.GameObjects.Graphics, objects: readonly WorldObject[], actors: readonly Actor[],
                               size: number, time: number): void {
  g.clear();
  for (const stage of objects) {
    if (stage.kind !== "stage") continue;
    const lit: boolean = performing(actors, stage);
    footlights(stage, size).forEach((light, index: number): void => {
      const strength: number = flicker(time, index * 1.9) * (lit ? 1.6 : 1);
      if (lit) for (let ring: number = 3; ring > 0; ring -= 1) g.fillStyle(0xf5a347, 0.07 * strength).fillCircle(light.x, light.y, ring * size * 0.4 * strength);
      const flame: number = (lit ? 5 : 3) * strength;
      g.fillStyle(0xf08a30).fillTriangle(light.x - 2, light.y, light.x + 2, light.y, light.x, light.y - flame - 1);
      g.fillStyle(0xfbd86a).fillTriangle(light.x - 1, light.y, light.x + 1, light.y, light.x, light.y - flame * 0.6);
    });
  }
}
