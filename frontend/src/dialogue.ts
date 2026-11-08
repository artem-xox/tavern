/** When the dialogue popup is open and to whom it speaks: a state machine over snapshots, clicks and keys. */
import type { PlayerTurn } from "./types";

/** `scene` and `turn` are the last ones seen while steering, so a popup closed with Esc reopens only on a new scene or turn. */
export interface DialogueState { open: boolean; to: string; scene: string | null; turn: PlayerTurn["state"] }

export type DialogueEvent =
  /** A snapshot: the played guest's scene, what it waits for, and whether the player holds the wheel. */
  | { kind: "snapshot"; scene: string | null; turn: PlayerTurn["state"]; steering: boolean }
  /** `reply`: a click on a member of the scene; `address`: the "To:" picker or a face. */
  | { kind: "reply" | "address"; to: string }
  /** `close`: Esc or the close button; `sent`: a line went out; `failed`: the world refused it. */
  | { kind: "close" | "sent" | "failed" };

export const CLOSED: DialogueState = { open: false, to: "auto", scene: null, turn: "none" };

/** The states in which the scene, the stage or a heckler waits for the player's words: arriving there opens the popup. */
const WAITING: ReadonlySet<PlayerTurn["state"]> = new Set(["your_turn", "comeback", "on_stage"]);

/** The popup after an event. */
export function dialogueStep(state: DialogueState, event: DialogueEvent): DialogueState {
  if (event.kind === "snapshot") return _seen(state, event);
  if (event.kind === "reply") return { ...state, open: true, to: event.to };
  if (event.kind === "address") return { ...state, to: event.to };
  return { ...state, open: event.kind === "failed" };
}

function _seen(state: DialogueState, event: { scene: string | null; turn: PlayerTurn["state"]; steering: boolean }): DialogueState {
  const { scene, turn } = event;
  if (!event.steering || (scene === null && !WAITING.has(turn))) return { ...CLOSED, turn: event.steering ? turn : "none" };
  if (scene !== state.scene) return { open: true, to: "auto", scene, turn };
  if (WAITING.has(turn) && turn !== state.turn) return { open: true, to: state.open ? state.to : "auto", scene, turn };
  return { ...state, turn };
}
