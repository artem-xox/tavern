import type { Command } from "./types";

export const MAX_GUESTS: number = 8;
export const DEFAULT_MINUTES: number = 5;
/** The evening lengths on offer, in minutes at the standard speed. */
export const MINUTE_CHOICES: readonly number[] = [3, 5, 10, 15, 30];

/** Pick a face, or put a picked one back; a ninth pick is ignored. */
export function togglePick(picked: readonly string[], id: string): string[] {
  if (picked.includes(id)) return picked.filter((item: string): boolean => item !== id);
  return picked.length >= MAX_GUESTS ? [...picked] : [...picked, id];
}

/** Whether the lineup may start: from one to eight guests. */
export function canStart(picked: readonly string[]): boolean {
  return picked.length >= 1 && picked.length <= MAX_GUESTS;
}

export function startCommand(cast: string, picked: readonly string[], minutes: number = DEFAULT_MINUTES): Command {
  return { type: "start", cast, guests: [...picked], minutes };
}
