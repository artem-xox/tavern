/** The fireplace: its stone surround in the wall, and the firelight it throws on the floor. */
import Phaser from "phaser";
import type { WorldObject } from "./types";

/** Which way a fireplace opens: away from the outer wall it is built into. */
export function hearthFacing(hearth: WorldObject, mapWidth: number): [number, number] {
  if (hearth.x === 0) return [1, 0];
  if (hearth.x + (hearth.width ?? 1) === mapWidth) return [-1, 0];
  return hearth.y === 0 ? [0, 1] : [0, -1];
}

/** Draw one fireplace into the wall it is built into. */
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

/** Let firelight flicker on the floor in front of each fireplace among `objects`. */
export function drawHearthGlow(g: Phaser.GameObjects.Graphics, objects: readonly WorldObject[], mapWidth: number, size: number, time: number): void {
  g.clear();
  const flicker: number = 0.82 + 0.1 * Math.sin(time / 170) + 0.08 * Math.sin(time / 53);
  for (const hearth of objects.filter((object: WorldObject): boolean => object.kind === "fireplace")) {
    // Light spills into the room on the side the fireplace opens to.
    const [dx, dy]: [number, number] = hearthFacing(hearth, mapWidth);
    const x: number = (hearth.x + (hearth.width ?? 1) / 2 + dx * 0.9) * size;
    const y: number = (hearth.y + (hearth.height ?? 1) / 2 + dy * 0.9) * size;
    for (let ring: number = 5; ring > 0; ring -= 1) {
      g.fillStyle(0xf5a347, 0.045 * flicker).fillCircle(x, y, ring * size * 0.62 * flicker);
    }
  }
}
