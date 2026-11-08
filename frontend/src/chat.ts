/** What the chat panel shows and sends, worked out from a snapshot: the scene's lines, who is in it, what the input says. */
import type { Actor, Command, Conversation, PlayerTurn, Snapshot, Turn } from "./types";

export interface ChatMember { id: string; name: string; face: string }
export interface ChatLine { speaker: string; addressee: string | null; words: string; mine: boolean }

export interface ChatModel {
  members: ChatMember[];
  lines: ChatLine[];
  state: PlayerTurn["state"];
  /** Real seconds before the turn passes in silence; null unless it is the player's turn. */
  secondsLeft: number | null;
  placeholder: string;
  enabled: boolean;
  /** Whether the hall's clock holds still for the player's line (auto-pause): no countdown runs. */
  held: boolean;
  /** Whether the "To:" picker shows (the stage speaks to the hall). */
  picker: boolean;
}

/** A ping at most every this many real seconds keeps the player's turn from passing while they type. */
export const PING_EVERY = 2;

const PLACEHOLDERS: Record<PlayerTurn["state"], string> = {
  none: "Click someone and choose Talk",
  free: "Say something…",
  your_turn: "Your turn",
  reading: "Being read…",
  on_stage: "Speak to the hall",
  comeback: "Answer the heckler",
};

/** The chat for a snapshot; null in an evening with no player. */
export function chatModel(snapshot: Snapshot): ChatModel | null {
  const turn: PlayerTurn | null = snapshot.player_turn;
  const { player, actors, conversations, time, speed } = snapshot.state;
  if (turn === null || player === null) return null;
  const scene: Conversation | undefined = conversations.find((item: Conversation): boolean => item.id === turn.scene_id);
  const names = new Map<string, Actor>(actors.map((actor: Actor): [string, Actor] => [actor.id, actor]));
  const nameOf = (id: string): string => names.get(id)?.name ?? id;
  const members: ChatMember[] = (scene?.participants ?? [])
    .filter((id: string): boolean => id !== player.actor_id && names.has(id))
    .map((id: string): ChatMember => ({ id, name: nameOf(id), face: names.get(id)?.sprite ?? id }));
  const lines: ChatLine[] = (scene?.turns ?? []).map((item: Turn): ChatLine => ({
    speaker: nameOf(item.speaker),
    addressee: item.addressee === null ? null : nameOf(item.addressee),
    words: item.act === "silence" ? "…" : item.line,
    mine: item.speaker === player.actor_id,
  }));
  const held: boolean = snapshot.turn_held === true;
  const secondsLeft: number | null = turn.silence_at === null || held ? null : Math.max(0, (turn.silence_at - time) / speed);
  const enabled: boolean = player.steering && turn.state !== "none" && turn.state !== "reading";
  return { members, lines, state: turn.state, secondsLeft, placeholder: PLACEHOLDERS[turn.state], enabled, held,
    picker: turn.state !== "on_stage" && turn.state !== "none" };
}

/** Whether to send a `typing` ping now: not within `PING_EVERY` of the last one, and only while the input has focus and text. */
export function nextPing(lastPingAt: number | null, now: number, hasText: boolean, focused: boolean): boolean {
  if (!hasText || !focused) return false;
  return lastPingAt === null || now - lastPingAt >= PING_EVERY;
}

/** The `say` command for typed text, or null when it is blank; `to` is `auto`, `everyone` or a member's ID. */
export function sayCommand(text: string, to: string): Command | null {
  const words: string = text.trim();
  return words === "" ? null : { type: "say", text: words, to };
}
