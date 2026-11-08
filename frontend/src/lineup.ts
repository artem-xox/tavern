import type { Command } from "./types";

export const MAX_GUESTS: number = 8;
export const DEFAULT_MINUTES: number = 5;
/** A played evening's length unless the person picks one: long enough to play a few scenes (600 game seconds). */
export const PLAY_MINUTES: number = 10;
/** The evening lengths on offer, in minutes at the standard speed. */
export const MINUTE_CHOICES: readonly number[] = [3, 5, 10, 15, 30];

/** The evening's length: the one the person chose, otherwise `PLAY_MINUTES` when they play a guest and `DEFAULT_MINUTES` when they watch. */
export function eveningMinutes(player: string | null, chosen: number | null): number {
  return chosen ?? (player === null ? DEFAULT_MINUTES : PLAY_MINUTES);
}

/** Pick a face, or put a picked one back; a ninth pick is ignored. */
export function togglePick(picked: readonly string[], id: string): string[] {
  if (picked.includes(id)) return picked.filter((item: string): boolean => item !== id);
  return picked.length >= MAX_GUESTS ? [...picked] : [...picked, id];
}

/** Whether the lineup may start: from one to eight guests. */
export function canStart(picked: readonly string[]): boolean {
  return picked.length >= 1 && picked.length <= MAX_GUESTS;
}

/** The played guest after a pick changed: kept while they are still picked, otherwise back to "Just watch" (null). */
export function keepPlayer(picked: readonly string[], player: string | null): string | null {
  return player !== null && picked.includes(player) ? player : null;
}

/** The start command; `player` is the picked guest the person plays, or null to just watch. */
export function startCommand(cast: string, picked: readonly string[], minutes: number = DEFAULT_MINUTES, player: string | null = null): Command {
  if (player !== null && !picked.includes(player)) throw new Error(`Cannot play ${player}: not one of the picked guests`);
  return { type: "start", cast, guests: [...picked], minutes, player };
}
