/** Drawing of the hall's furniture and fittings, one function per object kind. */
import Phaser from "phaser";
import type { WorldObject } from "./types";

/** Which way a fireplace opens: away from the outer wall it is built into. */
export function hearthFacing(hearth: WorldObject, mapWidth: number): [number, number] {
  if (hearth.x === 0) return [1, 0];
  if (hearth.x + (hearth.width ?? 1) === mapWidth) return [-1, 0];
  return hearth.y === 0 ? [0, 1] : [0, -1];
}

/** Two ivory dice over the reusable wooden table at the game's location. */
export function drawDice(g: Phaser.GameObjects.Graphics, object: WorldObject, size: number): void {
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
  const colors: [number, number][] = [[0x38544f, 0x8a9d79], [0x713b35, 0xbb7760], [0x354b69, 0x8999ac], [0x746035, 0xb09a60]];
  let ordinaryIndex: number = 0;
  objects.filter((object: WorldObject): boolean => object.kind === "table" || object.kind === "dice_table").forEach((table: WorldObject): void => {
    const [fill, trim] = table.kind === "dice_table" ? [0x2f5a3e, 0x9cc79a] : colors[ordinaryIndex++ % colors.length]!;
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
