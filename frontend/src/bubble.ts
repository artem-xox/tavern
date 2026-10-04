/** Speech bubbles: where one sits over its speaker, kept whole inside the map. */

/** Pixels the bubble keeps clear of the map edge, and its gap above a speaker's head or below their feet. */
const MARGIN = 4;
const ABOVE = 66;
const BELOW = 22;

/** Where to draw a bubble: its anchor point, and which edge of the bubble sits there (1 bottom, 0 top). */
export interface BubblePlacement {
  x: number;
  y: number;
  originY: 0 | 1;
}

/**
 * Place a bubble above a speaker, or below them when there is no room above.
 *
 * @param speakerX Speaker's x in map pixels.
 * @param speakerY Speaker's y in map pixels.
 * @param width Bubble width in pixels.
 * @param height Bubble height in pixels.
 * @param map Map size in pixels.
 * @returns Centre x, and the y of the bubble's bottom edge (above) or top edge (below). A bubble wider
 *   than the map is centred on it.
 */
export function placeBubble(speakerX: number, speakerY: number, width: number, height: number,
                            map: { width: number; height: number }): BubblePlacement {
  const half: number = width / 2;
  const x: number = map.width < width + 2 * MARGIN ? map.width / 2 : Math.min(Math.max(speakerX, MARGIN + half), map.width - MARGIN - half);
  if (speakerY - ABOVE - height >= MARGIN) return { x, y: speakerY - ABOVE, originY: 1 };
  return { x, y: Math.max(MARGIN, Math.min(speakerY + BELOW, map.height - MARGIN - height)), originY: 0 };
}

/** A bubble shows a line this many words at a time, so a long reply is read in pieces. */
const CHUNK_WORDS = 10;
/** Reading speed for a piece, in characters per second (the server's `chars_per_second`), and the least it stays up. */
const READ_CHARS_PER_SECOND = 15;
const MIN_CHUNK_MS = 1500;
/** How long the last piece stays up once its conversation is over, so it can still be read. */
export const LINGER_MS = 2000;

/**
 * Split a line into pieces of about eight to ten words, as even as possible (no one-word tail).
 *
 * @param line One spoken line.
 * @returns The line's pieces in order; empty for an empty line.
 */
export function splitLine(line: string): string[] {
  const words: string[] = line.split(/\s+/).filter((word: string): boolean => word !== "");
  const pieces: number = Math.ceil(words.length / CHUNK_WORDS);
  const size: number = Math.ceil(words.length / Math.max(pieces, 1));
  return Array.from({ length: pieces }, (_: unknown, index: number): string => words.slice(index * size, (index + 1) * size).join(" "));
}

/** How long a piece is shown, in milliseconds. */
export function chunkMs(chunk: string): number {
  return Math.max(MIN_CHUNK_MS, chunk.length / READ_CHARS_PER_SECOND * 1000);
}

/**
 * Which piece is up `elapsedMs` after the line began.
 *
 * @param chunks Pieces of the line, at least one.
 * @param elapsedMs Milliseconds since the first piece appeared.
 * @returns Index of the piece to show; the last one once all have had their time.
 */
export function chunkAt(chunks: readonly string[], elapsedMs: number): number {
  let left: number = elapsedMs;
  for (let index: number = 0; index < chunks.length - 1; index += 1) {
    left -= chunkMs(chunks[index]!);
    if (left < 0) return index;
  }
  return chunks.length - 1;
}

/** Milliseconds until every piece has had its time. */
export function lineMs(chunks: readonly string[]): number {
  return chunks.reduce((total: number, chunk: string): number => total + chunkMs(chunk), 0);
}
