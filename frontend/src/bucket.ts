/** The privy's bucket as a pixel map: a tapering stave bucket, two iron hoops, an iron bail and one tall stave. */
import { OUTLINE, outlined } from "./pixels.ts";

/** Colour of each key in `bucketRows`, as 0xRRGGBB. */
export const BUCKET_PALETTE: Readonly<Record<string, number>> = {
  [OUTLINE]: 0x24150f,
  r: 0xdcb27a, R: 0xb7834f, w: 0xc9935b,
  i: 0x2e1812, j: 0x4a2418,
  b: 0x6e1f17, B: 0x8e2e22, h: 0xb4673e, k: 0x45120e,
  S: 0xb6bfcc, s: 0x58606e, d: 0x2d3039,
};

const WIDTH = 22;
const CENTER: number = (WIDTH - 1) / 2;
const RIM = { y: 7, rx: 9.5, ry: 4.5, mouthRx: 7.9, mouthRy: 3.3 };
const BASE = { y: 21, rx: 8.3, ry: 3.5 };
const HOOPS: readonly number[] = [13, 19];
const STAVE = 3.2;

const inEllipse = (x: number, y: number, cy: number, rx: number, ry: number): boolean => ((x - CENTER) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1;
/** Half the body's width at a row: the bucket narrows toward its base. */
const half = (y: number): number => RIM.rx - ((RIM.rx - BASE.rx) * (y - RIM.y)) / (BASE.y - RIM.y);

function body(x: number, y: number): string {
  const reach: number = half(y);
  const across: number = (x - CENTER) / reach;
  for (const hoop of HOOPS) {
    // A hoop sags toward the viewer in the middle, where the bucket's belly turns to face us.
    const row: number = y - (hoop + 1.5 * (1 - across * across));
    if (row >= 0 && row < 1) return "S";
    if (row >= 1 && row < 2) return "s";
    if (row >= 2 && row < 3) return "d";
  }
  const slat: number = (x - (CENTER - reach)) / STAVE;
  if (slat % 1 < 1 / STAVE) return "k";
  if (across > 0.55) return "b";
  return across < -0.45 && Math.floor(slat) % 2 === 0 ? "h" : Math.floor(slat) % 2 === 0 ? "B" : "b";
}

function mouthOrRim(x: number, y: number): string {
  if (inEllipse(x, y, RIM.y + 0.5, RIM.mouthRx, RIM.mouthRy)) return y > RIM.y + 1 ? "j" : "i";
  return y > RIM.y ? "r" : "R";
}

/** A pixel of the bail: a bent iron rod from the left of the rim, up and over the mouth, with a lit top. */
function bail(x: number, y: number): string {
  const rod: [number, number][] = [[1, 9], [0, 8], [0, 7], [0, 6], [1, 5], [1, 4], [2, 3], [3, 2], [4, 1], [5, 1], [6, 1], [7, 2], [8, 3]];
  const at: number = rod.findIndex(([rx, ry]: [number, number]): boolean => rx === x && ry === y);
  return at < 0 ? "." : y <= 2 || at === 0 ? "S" : "s";
}

/**
 * The bucket, ringed with an outline.
 *
 * @returns Rows of equal length: `.` transparent, `OUTLINE` the ring, the other keys `BUCKET_PALETTE`.
 */
export function bucketRows(): string[] {
  const height: number = Math.ceil(BASE.y + BASE.ry) + 1;
  const plain: string[] = Array.from({ length: height }, (_: unknown, y: number): string => Array.from({ length: WIDTH }, (_: unknown, x: number): string => {
    const handle: string = bail(x, y);
    if (handle !== ".") return handle;
    if (inEllipse(x, y, RIM.y, RIM.rx, RIM.ry)) return mouthOrRim(x, y);
    if (y >= RIM.y && Math.abs(x - CENTER) <= half(y)) return body(x, y);
    if (inEllipse(x, y, BASE.y, BASE.rx, BASE.ry) && y > BASE.y) return y > BASE.y + 1.5 ? "k" : body(x, y);
    // The tall stave stands up behind the mouth on the right.
    return x >= 17 && x <= 19 && y >= 0 && y <= 5 ? "w" : ".";
  }).join(""));
  return outlined(plain);
}
