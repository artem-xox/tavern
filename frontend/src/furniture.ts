/** Drawing of the hall's furniture and fittings, one function per object kind. */
import Phaser from "phaser";
import type { WorldObject } from "./types";

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

export function drawToilet(g: Phaser.GameObjects.Graphics, x: number, y: number): void {
  g.fillStyle(0xa1aea0).fillRoundedRect(x - 10, y - 13, 20, 9, 3);
  g.fillStyle(0xe3e6cd).fillEllipse(x, y + 3, 21, 25);
  g.fillStyle(0x52685d).fillEllipse(x, y + 1, 12, 15);
  g.lineStyle(2, 0xf2eed9).strokeEllipse(x, y + 1, 15, 18);
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

/** The bare tabletop: shadow, rim, planks and inlay. */
function drawTableTop(g: Phaser.GameObjects.Graphics, object: WorldObject, size: number): void {
  const x: number = object.x * size;
  const y: number = object.y * size;
  const width: number = (object.width ?? 1) * size;
  const height: number = (object.height ?? 1) * size;
  g.fillStyle(0x33251d, 0.5).fillRoundedRect(x - 2, y + 5, width + 4, height, 8);
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
  const cy: number = (object.y + (object.height ?? 1) / 2) * size;
  drawDie(g, cx - 5, cy + 2, 3, -0.25);
  drawDie(g, cx + 6, cy - 3, 5, 0.35);
}

/** One die, turned by `tilt` radians, showing `pips` pips (1–6). */
function drawDie(g: Phaser.GameObjects.Graphics, x: number, y: number, pips: number, tilt: number): void {
  const side: number = 10;
  const corner = (dx: number, dy: number): { x: number; y: number } => ({
    x: x + dx * Math.cos(tilt) - dy * Math.sin(tilt), y: y + dx * Math.sin(tilt) + dy * Math.cos(tilt) });
  g.fillStyle(0x33251d, 0.4).fillRoundedRect(x - side / 2 + 1, y - side / 2 + 3, side, side, 2);
  const half: number = side / 2;
  g.fillStyle(0xf3ead2).fillPoints([corner(-half, -half), corner(half, -half), corner(half, half), corner(-half, half)], true);
  g.lineStyle(1, 0x8a7656).strokePoints([corner(-half, -half), corner(half, -half), corner(half, half), corner(-half, half)], true);
  const spots: [number, number][][] = [[[0, 0]], [[-2.5, -2.5], [2.5, 2.5]], [[-2.5, -2.5], [0, 0], [2.5, 2.5]],
    [[-2.5, -2.5], [2.5, -2.5], [-2.5, 2.5], [2.5, 2.5]], [[-2.5, -2.5], [2.5, -2.5], [0, 0], [-2.5, 2.5], [2.5, 2.5]],
    [[-2.5, -2.5], [2.5, -2.5], [-2.5, 0], [2.5, 0], [-2.5, 2.5], [2.5, 2.5]]];
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
  g.fillStyle(0x3b2b22).fillRoundedRect(x - 15, y - 16, 30, 33, 4);
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
