/** What the player's lines and acts caused on the people they touched, found by diffing two snapshots. */
import { INVITATION_WORDS } from "./readings.ts";
import type { Actor, InvitationKind, Snapshot, Thought, WorldEvent } from "./types";

/** A floating message: a `thought` over the guest who had it, a `toast` over the played guest. */
export interface Reaction { actor_id: string; kind: "thought" | "toast"; text: string }

const ANSWERS: Record<string, string> = { invitation_accepted: "accepted", invitation_declined: "declined" };

/** A signed number with a real minus sign: "+5", "−15". */
function signed(value: number): string {
  return value < 0 ? `−${-value}` : `+${value}`;
}

/** A thought's identity across snapshots: the server keeps no ID, and one guest never holds two equal ones. */
function key(item: Thought): string {
  return `${item.kind}|${item.about}|${item.expires_at}`;
}

function wellFormed(item: Thought): boolean {
  return typeof item.kind === "string" && Number.isFinite(item.opinion) && Number.isFinite(item.mood);
}

/** The reactions to one new thought a guest holds about the player. */
function fromThought(actor: Actor, item: Thought, player: Actor): Reaction[] {
  const change: string = item.opinion === 0 ? "" : ` ${signed(item.opinion)}`;
  const out: Reaction[] = [{ actor_id: actor.id, kind: "thought", text: `${item.kind.replaceAll("_", " ")} by ${player.name}${change}` }];
  const toast = (text: string): void => { out.push({ actor_id: player.id, kind: "toast", text }); };
  if (item.opinion !== 0) toast(`${actor.name} thinks ${item.opinion < 0 ? "worse" : "better"} of you ${signed(item.opinion)}`);
  if (item.mood !== 0) toast(`${actor.name}'s mood ${signed(item.mood)}`);
  if (item.kind === "quarrel") toast(`A quarrel with ${actor.name}`);
  return out;
}

/** The toast for an answer to the player's invitation, or null for any other event. */
function fromEvent(event: WorldEvent, player: Actor, names: Map<string, string>): Reaction | null {
  const answer: string | undefined = ANSWERS[event.type];
  if (answer === undefined || event.inviter_id !== player.id || event.actor_id === null) return null;
  const kind: string = INVITATION_WORDS[event.invitation as InvitationKind] ?? event.invitation ?? "";
  return { actor_id: player.id, kind: "toast", text: `${names.get(event.actor_id) ?? event.actor_id} ${answer}: ${kind}` };
}

/**
 * What the player caused between two snapshots: new thoughts other guests hold about the player (`about`), and
 * answers to the player's invitations (`inviter_id`). Nothing on the first snapshot, so a reload replays nothing.
 *
 * @param previous The snapshot before, or null for the first one.
 * @param next The snapshot now.
 * @returns Thoughts first, in actor order, then the invitation answers in log order.
 */
export function reactions(previous: Snapshot | null, next: Snapshot): Reaction[] {
  const playerId: string | undefined = next.state.player?.actor_id;
  const player: Actor | undefined = next.state.actors.find((item: Actor): boolean => item.id === playerId);
  if (previous === null || player === undefined) return [];
  const held: Map<string, Set<string>> = new Map(previous.state.actors.map(
    (actor: Actor): [string, Set<string>] => [actor.id, new Set(actor.thoughts.map(key))]));
  const out: Reaction[] = [];
  for (const actor of next.state.actors) {
    if (actor.id === player.id) continue;
    for (const item of actor.thoughts) {
      if (item.about === player.id && wellFormed(item) && !held.get(actor.id)?.has(key(item))) out.push(...fromThought(actor, item, player));
    }
  }
  const names: Map<string, string> = new Map(next.state.actors.map((actor: Actor): [string, string] => [actor.id, actor.name]));
  for (const event of next.state.events) {
    const reaction: Reaction | null = event.time > previous.state.time ? fromEvent(event, player, names) : null;
    if (reaction !== null) out.push(reaction);
  }
  return out;
}

/**
 * One message per figure, so reactions landing together do not float over each other.
 *
 * @param items Reactions in the order they should read.
 * @returns Per figure, in first-seen order, its distinct texts one per line.
 */
export function stacked(items: readonly Reaction[]): [string, string][] {
  const texts: Map<string, string[]> = new Map();
  for (const item of items) {
    const lines: string[] = texts.get(item.actor_id) ?? [];
    if (!lines.includes(item.text)) lines.push(item.text);
    texts.set(item.actor_id, lines);
  }
  return [...texts].map(([actor, lines]: [string, string[]]): [string, string] => [actor, lines.join("\n")]);
}
