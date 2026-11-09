/** What the client sends the server, and the server's reply to `options`. */
import type { Action } from "./types";

/** The reply to the `options` command: what is open to the played guest now, each action with its verb's label. */
export interface OptionsMessage {
  type: "options";
  target_id: string | null;
  options: { action: Action; label: string }[];
}

export type Command =
  | { type: "pause"; paused: boolean }
  | { type: "speed"; value: number }
  | { type: "refill"; object_id: string; amount: number }
  | { type: "block"; x: number; y: number; blocked: boolean }
  | { type: "force_action"; actor_id: string; action: Action }
  | { type: "start"; cast: string; guests: string[]; minutes: number; player: string | null }
  | { type: "steer"; on: boolean }
  | { type: "typing" }
  | { type: "let_pass" }
  | { type: "say"; text: string; to: "auto" | "everyone" | string }
  | { type: "act"; action: Action }
  | { type: "options"; target_id?: string }
  | { type: "save" | "load" | "reset" };
