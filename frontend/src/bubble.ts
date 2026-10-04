/** Speech bubbles: where one sits over its speaker, kept whole inside the map. */

/** Pixels the bubble keeps clear of the map edge, and its gap above a speaker's head or below their feet. */
const MARGIN = 4;
const ABOVE = 62;
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
