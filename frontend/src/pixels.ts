/** Pixel maps for art drawn in code: strings of equal length, `.` transparent, any other character a palette key. */

/** The palette key `outlined` gives the ring it draws; maps must not use it themselves. */
export const OUTLINE = "0";

/**
 * Ring a pixel map with a one-pixel outline, so it reads on any floor.
 *
 * A transparent pixel next to a filled one (above, below, left or right, not diagonally) becomes `OUTLINE`.
 * The result is one pixel larger on every side, so art may touch the edge of its map.
 *
 * @param rows The map: rows of equal length.
 * @returns The padded map with its outline; empty for no rows.
 * @throws Error The rows differ in length or use the `OUTLINE` key.
 */
export function outlined(rows: readonly string[]): string[] {
  if (rows.length === 0) return [];
  const width: number = rows[0]!.length;
  if (rows.some((row: string): boolean => row.length !== width)) throw new Error("Pixel map rows must all have the same length");
  if (rows.some((row: string): boolean => row.includes(OUTLINE))) throw new Error(`Pixel map key ${OUTLINE} is the outline's`);
  const filled = (x: number, y: number): boolean => y >= 0 && y < rows.length && x >= 0 && x < width && rows[y]![x] !== ".";
  const beside: [number, number][] = [[1, 0], [-1, 0], [0, 1], [0, -1]];
  return Array.from({ length: rows.length + 2 }, (_: unknown, row: number): string => Array.from({ length: width + 2 }, (_: unknown, column: number): string => {
    const x: number = column - 1;
    const y: number = row - 1;
    if (filled(x, y)) return rows[y]![x]!;
    return beside.some(([dx, dy]: [number, number]): boolean => filled(x + dx, y + dy)) ? OUTLINE : ".";
  }).join(""));
}
