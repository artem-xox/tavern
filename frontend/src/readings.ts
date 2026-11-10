/** How the world read each of the player's chat lines: the act, its target, and whether the reading was refused. */
import type { InvitationKind, Turn } from "./talk";
import type { WorldEvent } from "./types";

/** The chip under a line: `insult → Trump`, or a bare `remark` when the world refused the reading. */
export interface Reading { text: string; refused: boolean }

/** Short words for an invitation kind, after "invitation: ". */
export const INVITATION_WORDS: Record<InvitationKind, string> = {
  join_table: "table", darts_together: "darts", dice_together: "dice", buy_drink: "a drink",
  leave_together: "leaving", move_together: "moving",
};

// The acts whose plain name reads badly in a chip; any other act shows its name with spaces.
const ACT_WORDS: Record<string, string> = { share_news: "news", share_place: "a place", invite: "invitation" };

/**
 * The chip for one of the player's turns.
 *
 * @param turn The turn as the scene keeps it.
 * @param refused Whether the world refused the reader's answer and spoke the line as a remark.
 * @param nameOf A visitor's display name by ID.
 * @returns The chip, or null for a silence or a turn with no act.
 */
export function readingOf(turn: Turn, refused: boolean, nameOf: (id: string) => string): Reading | null {
  if (typeof turn.act !== "string" || turn.act === "" || turn.act === "silence") return null;
  if (refused) return { text: "remark", refused: true };
  const act: string = ACT_WORDS[turn.act] ?? turn.act.replaceAll("_", " ");
  const kind: string = turn.invitation === undefined ? "" : `: ${INVITATION_WORDS[turn.invitation] ?? turn.invitation}`;
  const to: string = turn.addressee === null ? "everyone" : nameOf(turn.addressee);
  return { text: `${act}${kind} → ${to}`, refused: false };
}

/**
 * Which of a scene's turns were the player's lines the world refused to read as meant.
 *
 * A refusal logs `misread` (with `speaker_id`) when the reading arrives; the line is spoken as a remark when it
 * falls due, so it is the player's first turn at or after that event. The world keeps only its latest events, so a
 * refusal older than the log reads as a remark as meant.
 *
 * @param turns The scene's turns, oldest first.
 * @param events The world's event log, oldest first.
 * @param playerId The played guest's ID.
 * @returns Indexes into `turns`.
 */
export function refusedTurns(turns: readonly Turn[], events: readonly WorldEvent[], playerId: string): Set<number> {
  const refused: Set<number> = new Set();
  for (const event of events) {
    if (event.type !== "misread" || event.speaker_id !== playerId) continue;
    const index: number = turns.findIndex((item: Turn): boolean => item.speaker === playerId && item.time >= event.time);
    if (index >= 0 && turns[index].act === "remark") refused.add(index);
  }
  return refused;
}
