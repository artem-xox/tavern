/** The player's line between Enter and the real turn: shown at once in the chat and over their head, until the turn lands. */
import type { Spoken } from "./bubble.ts";
import type { Conversation, Snapshot, WorldEvent } from "./types.ts";

/** A line the player sent and the server has not yet spoken: where it was said, and what the world looked like then. */
export interface PendingLine {
  text: string;
  /** The scene it was typed in; null for the stage (a number or a comeback). */
  sceneId: string | null;
  /** How many turns the scene had when it was sent: the player's next turn in it is this line. */
  turns: number;
  /** Game time it was sent. */
  sentAt: number;
}

/** The states in which a stage line is still waiting for the hall. */
const STAGE_STATES: readonly string[] = ["on_stage", "comeback"];

/** The pending line for text the player just sent, read against the snapshot they sent it from. */
export function pendingLine(text: string, snapshot: Snapshot): PendingLine {
  const sceneId: string | null = snapshot.player_turn?.scene_id ?? null;
  const scene: Conversation | undefined = snapshot.state.conversations.find((item: Conversation): boolean => item.id === sceneId);
  return { text, sceneId: scene ? sceneId : null, turns: scene?.turns.length ?? 0, sentAt: snapshot.state.time };
}

/**
 * Whether a pending line is still waiting in a newer snapshot.
 *
 * @returns The line while it waits; null once the real turn landed (a turn of the player's after it was sent), its
 *   scene ended or the player left it, the stage line was answered (an event of theirs with these words), or
 *   the player let go of the wheel.
 */
export function settle(pending: PendingLine | null, snapshot: Snapshot): PendingLine | null {
  const player = snapshot.state.player;
  if (pending === null || player === null || !player.steering) return null;
  if (pending.sceneId === null) {
    const said: boolean = snapshot.state.events.some((event: WorldEvent): boolean =>
      event.actor_id === player.actor_id && event.line === pending.text && event.time >= pending.sentAt);
    return said || !STAGE_STATES.includes(snapshot.player_turn?.state ?? "none") ? null : pending;
  }
  const scene: Conversation | undefined = snapshot.state.conversations.find((item: Conversation): boolean => item.id === pending.sceneId);
  if (scene === undefined || !scene.participants.includes(player.actor_id)) return null;
  const landed: boolean = scene.turns.slice(pending.turns).some((turn): boolean => turn.speaker === player.actor_id);
  return landed ? null : pending;
}

/** The pending line as a bubble over the played guest. */
export function pendingSpoken(pending: PendingLine, actorId: string): Spoken {
  return { speaker: actorId, line: pending.text, time: pending.sentAt };
}
