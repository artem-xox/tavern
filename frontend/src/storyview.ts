/** How the story score reads on the screen: one chip per kind of moment that happened. */

import type { Story } from "./types.ts";

const MARKS: Record<string, string> = {
  quarrel: "😡", fight: "👊", knockout: "💫", played_together: "🎲", gift: "🎁", fell_asleep: "💤", limped_home: "🩹",
};

/** The chips of the moments that happened, the most frequent first (equal counts keep the server's order). */
export function momentChips(story: Story): string[] {
  return Object.entries(story.moments)
    .filter(([, count]) => count > 0)
    .sort(([, a], [, b]) => b - a)
    .map(([kind, count]) => `${MARKS[kind] ?? "✨"} ${kind.replaceAll("_", " ")} ×${count}`);
}
