/** What the wheel bar and the "you" marker show: the played guest, who decides for them, and where the arrow floats. */
import type { World } from "./types";

/** The wheel bar's content: the played guest's art (a catalog sprite), name, who decides, and whether they are in the hall. */
export interface WheelState {
  face: string;
  name: string;
  steering: boolean;
  paused: boolean;
  present: boolean;
}

/** The bar for the world's player, or null with no player (or one the world does not know). */
export function wheelState(world: World): WheelState | null {
  const player = world.player;
  if (!player) return null;
  const inside = world.actors.find((actor) => actor.id === player.actor_id);
  const guest = inside ?? world.expected.find((item) => item.id === player.actor_id) ?? world.departed.find((actor) => actor.id === player.actor_id);
  if (!guest) return null;
  return { face: guest.sprite, name: guest.name, steering: player.steering, paused: world.paused, present: inside !== undefined };
}

/** Pixels above the figure's feet where the arrow hovers: over the name, which sits at -53. */
const MARKER_LIFT = 78;
const MARKER_BOB = 3;

/** Where the "you" arrow's tip goes for a figure drawn at (x, y) at `time` ms: above the head, bobbing gently. */
export function markerAt(x: number, y: number, time: number): { x: number; y: number } {
  return { x, y: y - MARKER_LIFT + MARKER_BOB * Math.sin(time / 260) };
}

/** The decision-source tag of the inspector: PLAYER while the person decides for the guest, otherwise Jev or local. */
export function decisionTag(source: string | undefined, steered: boolean): "PLAYER" | "JEV" | "LOCAL" {
  if (steered) return "PLAYER";
  return source === "jev" ? "JEV" : "LOCAL";
}
