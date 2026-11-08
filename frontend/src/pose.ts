/** Which pose a visitor is drawn in, from their body, what they are doing and who is doing what to them. */
import { fightPose, type Body } from "./fightview.ts";

/** What the pose of a visitor depends on: the wound fields, their id and the target of their action. */
export interface PoseActor extends Body {
  id: string;
  action: { verb: string; target_id: string | null } | null;
}

/** The parts of the world that bear on a pose: who gives to whom, and who is chatting. */
export interface PoseWorld {
  actors: readonly PoseActor[];
  conversations: readonly { participants: readonly string[] }[];
}

/** The seated version of a standing pose, for a visitor who does it from their seat. */
const SEATED_POSES: Readonly<Record<string, string>> = { Drinking: "DrinkingSeated", Talking: "TalkingSeated", Giving: "GivingSeated", Receiving: "ReceivingSeated" };
/** Poses drawn low on the cell, as a seated figure sits. */
const LOW_POSES: readonly string[] = ["Seated", "SleepingSeated", "Bathroom", "HurtSeated", "KnockedOut", ...Object.values(SEATED_POSES)];

/** Whether a pose is drawn low on its cell. */
export function isLow(pose: string): boolean {
  return LOW_POSES.includes(pose);
}

/** A visitor using the WC sits on the pot, facing south, in the ordinary seated pose. */
export function onPot(actor: PoseActor): boolean {
  return actor.status === "interacting" && actor.action?.verb === "use_toilet";
}

/**
 * The pose a visitor is drawn in. A wound wins over everything, then walking, the pot, being handed something,
 * the pose of their activity (seated version from a chair), a seated chat, and last standing or sitting idle.
 */
export function poseOf(actor: PoseActor, world: PoseWorld | null, activities: Readonly<Record<string, { pose: string | null }>>): string {
  const wound: string | null = fightPose(actor);
  if (wound) return wound;
  if (actor.status === "walking") return "Walking";
  if (onPot(actor)) return "Seated";
  // Someone handing this visitor something holds it out to them; they reach for it, whatever they were doing.
  const offered: boolean = world?.actors.some((giver: PoseActor): boolean => giver.status === "interacting" && giver.action?.verb === "give" && giver.action.target_id === actor.id) ?? false;
  const pose: string | null | undefined = offered ? "Receiving" : actor.status === "interacting" && actor.action ? activities[actor.action.verb]?.pose : null;
  if (pose) return actor.seat_id ? SEATED_POSES[pose] ?? pose : pose;
  const chatting: boolean = world?.conversations.some((scene): boolean => scene.participants.includes(actor.id)) ?? false;
  return actor.seat_id ? chatting ? "TalkingSeated" : "Seated" : "Idle";
}
