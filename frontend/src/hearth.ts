/** The fireplace: a stone surround with a hearth and logs, the flames above it, and the firelight on the floor. */
import type Phaser from "phaser";
import type { WorldObject } from "./types";

/** Which way a fireplace opens: away from the outer wall it is built into. */
export function hearthFacing(hearth: Pick<WorldObject, "x" | "y" | "width">, mapWidth: number): [number, number] {
  if (hearth.x === 0) return [1, 0];
  if (hearth.x + (hearth.width ?? 1) === mapWidth) return [-1, 0];
  return hearth.y === 0 ? [0, 1] : [0, -1];
}

type Point = [number, number];

/**
 * A fireplace in its own coordinates, so one drawing serves any wall: `u` runs along the wall it is built
 * into, and `v` from the wall's far side out to the room's edge of its cells.
 */
export interface Frame {
  length: number;
  depth: number;
  at: (u: number, v: number) => { x: number; y: number };
}

export function frameOf(hearth: WorldObject, size: number, mapWidth: number): Frame {
  const [dx, dy]: [number, number] = hearthFacing(hearth, mapWidth);
  const x0: number = hearth.x * size;
  const y0: number = hearth.y * size;
  const w: number = (hearth.width ?? 1) * size;
  const h: number = (hearth.height ?? 1) * size;
  if (dy === 1) return { length: w, depth: h, at: (u: number, v: number) => ({ x: x0 + u, y: y0 + v }) };
  if (dy === -1) return { length: w, depth: h, at: (u: number, v: number) => ({ x: x0 + w - u, y: y0 + h - v }) };
  if (dx === 1) return { length: h, depth: w, at: (u: number, v: number) => ({ x: x0 + v, y: y0 + u }) };
  return { length: h, depth: w, at: (u: number, v: number) => ({ x: x0 + w - v, y: y0 + h - u }) };
}

function fillPolygon(g: Phaser.GameObjects.Graphics, frame: Frame, color: number, points: Point[], alpha: number = 1): void {
  g.fillStyle(color, alpha).fillPoints(points.map(([u, v]: Point) => frame.at(u, v)), true);
}

function box(u: number, v: number, width: number, height: number): Point[] {
  return [[u, v], [u + width, v], [u + width, v + height], [u, v + height]];
}

/** A log: a bar of `thick` between two points, with a pale ring at its second end. */
function drawLog(g: Phaser.GameObjects.Graphics, frame: Frame, from: Point, to: Point, thick: number, bark: number): void {
  const length: number = Math.hypot(to[0] - from[0], to[1] - from[1]);
  const nu: number = -(to[1] - from[1]) / length * thick / 2;
  const nv: number = (to[0] - from[0]) / length * thick / 2;
  fillPolygon(g, frame, bark, [[from[0] + nu, from[1] + nv], [to[0] + nu, to[1] + nv], [to[0] - nu, to[1] - nv], [from[0] - nu, from[1] - nv]]);
  const end = frame.at(to[0], to[1]);
  g.fillStyle(0xb98d5c).fillCircle(end.x, end.y, thick / 2);
  g.fillStyle(0x7a5638).fillCircle(end.x, end.y, thick / 4);
}

const MORTAR = 0x3a352f;
const STONES: readonly number[] = [0x625a50, 0x6d645a, 0x585148];
/** Stone courses are this many pixels high and blocks this wide; each course is shifted half a block. */
const COURSE = 8;
const BLOCK = 12;

/**
 * Draw one fireplace into the wall it is built into: dressed stone in courses, a timber mantel, an arched
 * sooty opening with a hearthstone lip, andirons and two crossed logs. The flames are `drawFlames`, redrawn each frame.
 *
 * @param g Layer for the static furniture.
 * @param hearth The `fireplace` object.
 * @param size Tile size in pixels.
 * @param mapWidth Hall width in cells, which tells which wall the fireplace is in.
 */
export function drawFireplace(g: Phaser.GameObjects.Graphics, hearth: WorldObject, size: number, mapWidth: number): void {
  const f: Frame = frameOf(hearth, size, mapWidth);
  const length: number = f.length;
  const depth: number = f.depth;
  const mid: number = length / 2;
  const opening: number = length * 0.64;
  const left: number = mid - opening / 2;
  const right: number = mid + opening / 2;
  const apex: number = 7;
  const shoulder: number = 14;
  // Stone: mortar underneath, each block a shade lighter with a one-pixel gap.
  fillPolygon(g, f, MORTAR, box(-3, -1, length + 6, depth + 1));
  for (let course: number = 0; course * COURSE < depth; course += 1) {
    const shift: number = (course % 2) * (BLOCK / 2);
    for (let start: number = -3 - shift, index: number = 0; start < length + 3; start += BLOCK, index += 1) {
      const from: number = Math.max(start, -3);
      const to: number = Math.min(start + BLOCK, length + 3);
      fillPolygon(g, f, STONES[(index + course) % STONES.length]!, box(from + 0.5, course * COURSE + 0.5, to - from - 1, COURSE - 1));
    }
  }
  // Timber mantel across the top, lit from above.
  fillPolygon(g, f, 0x4a3220, box(-5, -2, length + 10, 6));
  fillPolygon(g, f, 0x8a6340, box(-5, -2, length + 10, 1.5));
  fillPolygon(g, f, 0x1f150d, box(-5, 4, length + 10, 1.5), 0.6);
  // Arched opening, dark with soot, and a warm patch where the fire lights its back wall.
  const arch: Point[] = Array.from({ length: 11 }, (_: unknown, step: number): Point => {
    const angle: number = Math.PI * step / 10;
    return [mid - Math.cos(angle) * opening / 2, shoulder - Math.sin(angle) * (shoulder - apex)];
  });
  fillPolygon(g, f, 0x120c09, [[left, depth + 1], [left, shoulder], ...arch, [right, shoulder], [right, depth + 1]]);
  fillPolygon(g, f, 0x2a160d, box(left + 5, shoulder - 1, opening - 10, depth - shoulder - 2));
  fillPolygon(g, f, 0x4a2412, box(left + 10, shoulder + 5, opening - 20, depth - shoulder - 8));
  // Hearthstone lip on the room side, with a shadow beyond it.
  fillPolygon(g, f, 0x1e1914, box(left - 5, depth + 2, opening + 10, 2), 0.35);
  fillPolygon(g, f, 0x8c8276, box(left - 5, depth - 3, opening + 10, 5));
  fillPolygon(g, f, 0xb0a595, box(left - 5, depth - 3, opening + 10, 1));
  // Two crossed logs on a bed of coals, between two iron andirons.
  fillPolygon(g, f, 0xc2381d, box(mid - 17, depth - 7, 34, 3), 0.9);
  drawLog(g, f, [mid - 18, depth - 8], [mid + 16, depth - 12], 5, 0x5a3b25);
  drawLog(g, f, [mid + 18, depth - 8], [mid - 15, depth - 12], 5, 0x6b4630);
  for (const post of [left + 4, right - 7]) {
    fillPolygon(g, f, 0x1a1a1a, box(post, depth - 12, 3, 9));
    const ball = f.at(post + 1.5, depth - 12);
    g.fillStyle(0x4a4a48).fillCircle(ball.x, ball.y, 2);
  }
}

/** Flame tongues, from the widest and reddest outer one to the small yellow core; `scale` shrinks each layer. */
const FLAME_LAYERS: readonly { color: number; scale: number }[] = [
  { color: 0xc8381f, scale: 1 }, { color: 0xf08a30, scale: 0.72 }, { color: 0xfbd86a, scale: 0.42 },
];
/** Offset along the wall, height, width and flicker phase of each tongue. */
const TONGUES: readonly { along: number; height: number; width: number; phase: number }[] = [
  { along: -13, height: 6, width: 7, phase: 0 }, { along: -6, height: 11, width: 9, phase: 1.7 }, { along: 0, height: 13, width: 10, phase: 3.1 },
  { along: 6, height: 10, width: 9, phase: 4.4 }, { along: 13, height: 6, width: 7, phase: 5.8 },
];
const EMBERS = 5;

/**
 * Draw the flames and the sparks above the logs of each fireplace among `objects`, replacing the last frame's.
 *
 * Each tongue flickers on its own phase, so the fire never moves as one block.
 *
 * @param g Layer for the flames, above the static furniture and cleared here.
 * @param objects Every object of the hall; only fireplaces draw.
 * @param mapWidth Hall width in cells.
 * @param size Tile size in pixels.
 * @param time Real time in milliseconds, which drives the flicker.
 */
export function drawFlames(g: Phaser.GameObjects.Graphics, objects: readonly WorldObject[], mapWidth: number, size: number, time: number): void {
  g.clear();
  for (const hearth of objects.filter((object: WorldObject): boolean => object.kind === "fireplace")) {
    const f: Frame = frameOf(hearth, size, mapWidth);
    const mid: number = f.length / 2;
    const base: number = f.depth - 8;
    const bed = f.at(mid, base + 1);
    g.fillStyle(0xff7a30, 0.4 + 0.1 * Math.sin(time / 120)).fillEllipse(bed.x, bed.y, 32, 6);
    for (const layer of FLAME_LAYERS) {
      for (const tongue of TONGUES) {
        const flicker: number = 1 + 0.18 * Math.sin(time / 95 + tongue.phase) + 0.1 * Math.sin(time / 41 + tongue.phase * 2);
        const height: number = tongue.height * layer.scale * flicker;
        const width: number = tongue.width * layer.scale;
        const sway: number = 2 * layer.scale * Math.sin(time / 160 + tongue.phase);
        const root = f.at(mid + tongue.along, base);
        g.fillStyle(layer.color).fillPoints([
          { x: root.x - width / 2, y: root.y }, { x: root.x - width * 0.62, y: root.y - height * 0.35 }, { x: root.x + sway, y: root.y - height },
          { x: root.x + width * 0.62, y: root.y - height * 0.35 }, { x: root.x + width / 2, y: root.y },
        ], true);
      }
    }
    for (let spark: number = 0; spark < EMBERS; spark += 1) {
      const age: number = (time / 1100 + spark * 0.21) % 1;
      const at = f.at(mid + Math.sin(spark * 2.3 + time / 500) * 9, base - 3 - age * 11);
      g.fillStyle(0xffc060, 0.9 * (1 - age)).fillRect(at.x - 0.75, at.y - 0.75, 1.5, 1.5);
    }
  }
}

/** How strongly a flame burns at a real time in milliseconds, around 0.8; a different `phase` keeps two flames from flickering in step. */
export function flicker(time: number, phase: number = 0): number {
  return 0.82 + 0.1 * Math.sin(time / 170 + phase) + 0.08 * Math.sin(time / 53 + phase * 1.7);
}

/** How far the firelight reaches into the room, in cells: the outermost of five rings. */
export const HEARTH_GLOW_RADIUS = 5 * 0.62;

/** Let firelight flicker on the floor in front of each fireplace among `objects`. */
export function drawHearthGlow(g: Phaser.GameObjects.Graphics, objects: readonly WorldObject[], mapWidth: number, size: number, time: number): void {
  g.clear();
  const strength: number = flicker(time);
  for (const hearth of objects.filter((object: WorldObject): boolean => object.kind === "fireplace")) {
    // Light spills into the room on the side the fireplace opens to.
    const [dx, dy]: [number, number] = hearthFacing(hearth, mapWidth);
    const x: number = (hearth.x + (hearth.width ?? 1) / 2 + dx * 0.9) * size;
    const y: number = (hearth.y + (hearth.height ?? 1) / 2 + dy * 0.9) * size;
    for (let ring: number = 5; ring > 0; ring -= 1) {
      g.fillStyle(0xf5a347, 0.045 * strength).fillCircle(x, y, ring * size * 0.62 * strength);
    }
  }
}
