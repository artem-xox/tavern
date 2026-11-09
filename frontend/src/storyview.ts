/** How the story score reads on the screen: one chip per kind of moment that happened. */

import type { CitedEvent, Retelling, Story } from "./story.ts";

const MARKS: Record<string, string> = {
  quarrel: "😡", fight: "👊", knockout: "💫", played_together: "🎲", gift: "🎁", fell_asleep: "💤", limped_home: "🩹", got_drunk: "🥴",
};

/** The chips of the moments that happened, the most frequent first (equal counts keep the server's order). */
export function momentChips(story: Story): string[] {
  return Object.entries(story.moments)
    .filter(([, count]) => count > 0)
    .sort(([, a], [, b]) => b - a)
    .map(([kind, count]) => `${MARKS[kind] ?? "✨"} ${kind.replaceAll("_", " ")} ×${count}`);
}

/** What the closing window shows: nothing, a request to wait while the storyteller works, or the finished retelling. */
export type RetellingWindow = "hidden" | "waiting" | "told";

/** Waiting cannot be closed (the guest has nothing else to read); a told retelling stays closed once dismissed. */
export function retellingWindow(telling: boolean, retelling: Retelling | null, dismissed: boolean): RetellingWindow {
  if (telling) return "waiting";
  return retelling !== null && !dismissed ? "told" : "hidden";
}

/** The chapters (by index) that cite a line the player typed or an act the player chose; none without a player. */
export function playerChapters(retelling: Retelling, events: Readonly<Record<number, CitedEvent>>, playerId: string | null): number[] {
  if (playerId === null) return [];
  const theirs = (position: number): boolean => {
    const event = events[position];
    return event !== undefined && (event.player || (event.type === "player_act" && event.actor_id === playerId));
  };
  return retelling.chapters.flatMap((chapter, index) => (chapter.events.some(theirs) ? [index] : []));
}

/** The guests of a chapter with the played one first, when they are among them. */
export function playerFirst(actorIds: readonly string[], playerId: string | null): string[] {
  if (playerId === null || !actorIds.includes(playerId)) return [...actorIds];
  return [playerId, ...actorIds.filter((id) => id !== playerId)];
}
