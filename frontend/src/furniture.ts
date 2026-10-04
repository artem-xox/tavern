/** Drawing of the hall's furniture and fittings, one function per object kind. */
import Phaser from "phaser";
import type { WorldObject } from "./types";

/** Which way a fireplace opens: away from the outer wall it is built into. */
export function hearthFacing(hearth: WorldObject, mapWidth: number): [number, number] {
  if (hearth.x === 0) return [1, 0];
  if (hearth.x + (hearth.width ?? 1) === mapWidth) return [-1, 0];
  return hearth.y === 0 ? [0, 1] : [0, -1];
}

export function drawDoor(g: Phaser.GameObjects.Graphics, floor: Phaser.GameObjects.Graphics, door: WorldObject, size: number): void {
  const x: number = (door.x - 0.3) * size;
  const y: number = door.y * size;
  floor.fillStyle(0x41372a).fillRoundedRect((door.x - 1) * size, (door.y - 1.2) * size, 3 * size, size * 0.7, 3);
  floor.lineStyle(1, 0xb29762, 0.6).strokeRoundedRect((door.x - 0.85) * size, (door.y - 1.1) * size, 2.7 * size, size * 0.5, 2);
  g.fillStyle(0x634835).fillRoundedRect(x, y + 1, 1.6 * size, 26, 3);
  for (let plank: number = 1; plank < 4; plank += 1) {
    g.lineStyle(1, 0xc0a16d, 0.5).lineBetween(x + plank * 0.4 * size, y + 5, x + plank * 0.4 * size, y + 25);
  }
  g.fillStyle(0xe2c27a).fillCircle(x + 1.6 * size - 9, y + 15, 2);
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

export function drawFireplace(g: Phaser.GameObjects.Graphics, hearth: WorldObject, size: number, mapWidth: number): void {
  const x: number = hearth.x * size;
  const y: number = hearth.y * size;
  const width: number = (hearth.width ?? 1) * size;
  const height: number = (hearth.height ?? 1) * size;
  const [dx, dy]: [number, number] = hearthFacing(hearth, mapWidth);
  // Stone surround in the wall, with a hearthstone lip on the room side.
  g.fillStyle(0x6d645b).fillRoundedRect(x - 3, y - 3, width + 6, height + 6, 4);
  g.lineStyle(1, 0x8d8378, 0.7).strokeRoundedRect(x, y, width, height, 3);
  g.fillStyle(0x857b70).fillRect(x + (dx < 0 ? -6 : dx > 0 ? width : 0), y + (dy < 0 ? -6 : dy > 0 ? height : 0),
    dx === 0 ? width : 6, dy === 0 ? height : 6);
  // Firebox with logs and layered flames.
  const cx: number = x + width / 2;
  const cy: number = y + height / 2;
  const span: number = Math.min(width, height) * 0.62;
  const reach: number = Math.max(width, height) * 0.7;
  g.fillStyle(0x1f1612).fillRoundedRect(cx - (dx === 0 ? reach : span) / 2, cy - (dy === 0 ? reach : span) / 2,
    dx === 0 ? reach : span, dy === 0 ? reach : span, 6);
  g.fillStyle(0x5a3b25).fillRoundedRect(cx - 9, cy - 3, 18, 6, 2);
  g.fillStyle(0xe2763a).fillEllipse(cx - 3, cy - 1, 14, 20);
  g.fillStyle(0xf09a3e).fillEllipse(cx + 4, cy - 2, 11, 16);
  g.fillStyle(0xf8d06a).fillEllipse(cx, cy, 7, 11);
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

export function drawTable(g: Phaser.GameObjects.Graphics, object: WorldObject, size: number): void {
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
  g.fillStyle(0xe8dbc0).fillRoundedRect(x + width - 19, y + height - 19, 11, 10, 1);
  drawMug(g, x + 13, y + 13);
  drawMug(g, x + width - 13, y + height - 12);
  const cx: number = x + width / 2;
  const cy: number = y + height / 2;
  g.fillStyle(0xf8d281, 0.1).fillCircle(cx, cy, 18);
  g.fillStyle(0x69553a).fillEllipse(cx, cy + 3, 14, 8);
  g.fillStyle(0xf2dfae).fillRect(cx - 2, cy - 6, 4, 10);
  g.fillStyle(0xffd884).fillEllipse(cx, cy - 8, 4, 7);
}

/** Lay a rug under every table and its chairs, kept clear of the walls. */
export function drawRugs(floor: Phaser.GameObjects.Graphics, objects: WorldObject[], size: number): void {
  const palette: [number, number][] = [[0x8d463a, 0xd2a367], [0x526455, 0xabbd92], [0x4b5874, 0xa9b6cf], [0x7b5b30, 0xd9b26b]];
  objects.filter((object: WorldObject): boolean => object.kind === "table").forEach((table: WorldObject, index: number): void => {
    const [fill, trim] = palette[index % palette.length]!;
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
