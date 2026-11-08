/** Skip ahead: run the hall fast until something concerns the played guest, told from snapshot and event fields. */
import type { Snapshot, World, WorldEvent } from "./types.ts";

/** The speed a skip runs the hall at: the fastest the server allows. */
export const SKIP_SPEED = 8;
/** Game seconds a skip runs at most before it drops back to normal speed. */
export const SKIP_CAP = 180;

/** A skip under way: the game time it began, and the speed to come back to. */
export interface Skip {
  since: number;
  speed: number;
}

/** Why a skip stops: the player's line is due, a line or an invitation is for them, trouble starts, the cap, or it was called off. */
export type SkipStop = "your_turn" | "addressed" | "invited" | "quarrel" | "fight" | "cap" | "over";

/** What the played guest is told when a skip stops; nothing when it was called off. */
export const SKIP_WORDS: Readonly<Record<SkipStop, string | null>> = {
  your_turn: "Your line", addressed: "Someone speaks to you", invited: "An invitation for you",
  quarrel: "A quarrel breaks out", fight: "A fight starts", cap: "A quiet stretch passed", over: null,
};

/** Whether a skip may start: the player holds the wheel, the hall runs, and no line of theirs is due. */
export function canSkip(snapshot: Snapshot): boolean {
  return snapshot.state.player?.steering === true && !snapshot.state.paused && !DUE.includes(snapshot.player_turn?.state ?? "none");
}

/** The player-turn states in which a line of the player's is due. */
const DUE: readonly string[] = ["your_turn", "comeback"];
/** The events of trouble in the hall that stop a skip, whoever is in them. */
const TROUBLE: Readonly<Record<string, SkipStop>> = { quarrel: "quarrel", fight_started: "fight" };

/** A skip that starts now, from the world's time and speed. */
export function skipFrom(world: World): Skip {
  return { since: world.time, speed: world.speed };
}

/**
 * Whether a skip stops at this snapshot, and why.
 *
 * @param cap Game seconds after its start a skip stops anyway.
 * @returns `over` when nobody is at the wheel or the hall was paused by hand (not held for the player's line);
 *   `your_turn` when their line is due; for an event after the skip began, `invited` or `addressed` (a `turn`
 *   addressed to the played guest, an `invite` act or another), or `quarrel` / `fight` (anyone's); `cap` once
 *   `cap` game seconds have passed; null while the skip runs on.
 */
export function skipStop(skip: Skip, snapshot: Snapshot, cap: number = SKIP_CAP): SkipStop | null {
  const world: World = snapshot.state;
  const player = world.player;
  if (player === null || !player.steering || (world.paused && !snapshot.turn_held)) return "over";
  if (DUE.includes(snapshot.player_turn?.state ?? "none")) return "your_turn";
  for (const event of world.events) {
    if (event.time <= skip.since) continue;
    const stop: SkipStop | null = eventStop(event, player.actor_id);
    if (stop !== null) return stop;
  }
  return world.time - skip.since >= cap ? "cap" : null;
}

function eventStop(event: WorldEvent, playerId: string): SkipStop | null {
  if (event.type === "turn" && event.addressee === playerId && event.actor_id !== playerId) return event.act === "invite" ? "invited" : "addressed";
  return TROUBLE[event.type] ?? null;
}
