/** What the inspector makes of a visitor's inner state: pips for needs, merged thoughts, opinion bars. */
import type { Thought } from "./types";

/** A need is shown as this many pips of satisfaction. */
export const NEED_PIPS = 5;
const WORDS: readonly string[] = ["desperate", "very low", "low", "fine", "good", "full"];

/**
 * How many of five pips a need fills, the more content the fuller.
 *
 * The server counts needs as urgency (0 calm, 100 desperate); the inspector draws them the other way up, as a
 * bar that is full when the guest is fine.
 *
 * @param urgency The need's urgency; a value outside 0–100 is held to it.
 * @returns A whole number from 0 to 5; exact halves round up (50 is three).
 * @throws RangeError The urgency is not a number.
 */
export function needPips(urgency: number): number {
  if (Number.isNaN(urgency)) throw new RangeError("A need's urgency must be a number");
  const held: number = Math.min(100, Math.max(0, urgency));
  return Math.round((100 - held) / (100 / NEED_PIPS));
}

/** A word for a need with `pips` filled. */
export function needWord(pips: number): string {
  return WORDS[pips]!;
}

/** How a need is coloured: empty or one pip is `bad`, two `warn`, three or more `good`. */
export function needTone(pips: number): "bad" | "warn" | "good" {
  return pips <= 1 ? "bad" : pips === 2 ? "warn" : "good";
}

/** A thought as shown: one row for every thought with the same words. */
export interface MergedThought {
  text: string;
  /** The moods of every thought of these words, added. */
  mood: number;
  count: number;
}

/**
 * Merge thoughts with the same words into one row each, in the order they first appear.
 *
 * @param thoughts The active thoughts, oldest first.
 * @returns One row per distinct text, with its count and the sum of its moods.
 */
export function mergeThoughts(thoughts: readonly Thought[]): MergedThought[] {
  const rows: Map<string, MergedThought> = new Map();
  for (const thought of thoughts) {
    const row: MergedThought | undefined = rows.get(thought.text);
    if (row) { row.mood += thought.mood; row.count += 1; } else rows.set(thought.text, { text: thought.text, mood: thought.mood, count: 1 });
  }
  return [...rows.values()];
}

/**
 * Where an opinion's bar grows from the middle of its track.
 *
 * @param opinion An opinion from −100 to 100; one beyond is held to it.
 * @returns The side the bar grows toward, and its length as a percentage of the whole track (at most 50).
 */
export function opinionBar(opinion: number): { side: "left" | "right"; percent: number } {
  const held: number = Math.min(100, Math.max(-100, opinion));
  return { side: held < 0 ? "left" : "right", percent: Math.abs(held) / 2 };
}
