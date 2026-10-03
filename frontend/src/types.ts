export type Cell = [number, number];
/** An action verb; the server's activity table lists the verbs it runs. */
export type Verb = string;
export type Mode = "local" | "jev";

export interface WorldObject {
  id: string;
  kind: "tap" | "toilet" | "chair" | "bar" | "table" | "darts" | "door" | "window" | "fireplace";
  name: string;
  x: number;
  y: number;
  width?: number;
  height?: number;
  walkable?: boolean;
  table_id?: string;
  facing?: "north" | "south" | "east" | "west";
  interaction_spots: Cell[];
  stock: number | null;
  reserved_by: string | null;
  /** Cells a line stands on, front first, for places used one visitor at a time. */
  queue_spots?: Cell[];
  /** Who waits in that line, front first, and since when (game seconds). */
  queue?: { actor_id: string; since: number }[];
  appeal?: number;
  comforts?: string[];
  reach?: number;
}

/** How the client names, shows, and targets one verb, as described by the server. */
export interface ActivityView {
  label: string;
  status: string | null;
  pose: string | null;
  target_kinds: WorldObject["kind"][];
  partner: boolean;
}

export interface DecisionStage {
  source: Mode;
  scores: unknown;
  error: string | null;
}

/** The second stage after choosing a family of several actions, such as a pastime. */
export interface FamilyStage extends DecisionStage {
  name: string;
}

export interface Action {
  id: string;
  verb: Verb;
  target_id: string | null;
}

export interface Actor {
  id: string;
  name: string;
  color: string | number;
  /** Character art under /characters; the scene falls back to the generic visitor. */
  sprite: string;
  x: number;
  y: number;
  traits: Record<string, unknown>;
  needs: { thirst: number; fatigue: number; bladder: number; social: number; boredom: number };
  inventory: { beer: number };
  status: "idle" | "walking" | "interacting" | "waiting" | "queued";
  action: Action | null;
  seat_id: string | null;
  favorite_seat_id: string | null;
  visit: { seconds: number; beers: number; grievances: string[]; left_at?: number };
  path: Cell[];
  knowledge: { objects: Record<string, Record<string, unknown>> };
  memory: unknown[];
  decision: (DecisionStage & { seat?: DecisionStage; family?: FamilyStage }) | null;
  /** Where the server turns the visitor; null keeps the seat's, the task's, or the walking direction. */
  facing: Facing | null;
  /** A cell the visitor looks at until a game time, drawn by a stimulus. */
  gaze: { cell: Cell; until: number; stimulus_id: number } | null;
  emote: { kind: EmoteKind; until: number } | null;
  /** Game time of the last interrupt that asked for a fresh decision. */
  interrupted_at: number | null;
}

export type Facing = "north" | "south" | "east" | "west";
export type EmoteKind = "alert" | "confused" | "angry" | "affection" | "sleep" | "waiting";

/** A scenario guest still on the way, with tonight's needs already drawn. */
export interface ExpectedGuest {
  id: string;
  name: string;
  color: string;
  sprite: string;
  traits: Record<string, number>;
  needs: Partial<Actor["needs"]>;
  /** Game seconds after opening. */
  arrives_at: number;
}

export interface WorldEvent {
  time: number;
  actor_id: string | null;
  type: string;
  message: string;
}

/** A sound in the hall waiting for the listeners' attention at the end of the tick. */
export interface Stimulus {
  id: number;
  kind: string;
  noun: string;
  /** Visitors who made it; empty for a call from a place. */
  sources: string[];
  cell: Cell;
  loudness: number;
  reach: number;
  time: number;
  /** Visitors it concerns without having made it. */
  about: string[];
  cause: string;
  event: string | null;
}

/** One spoken line of a conversation scene; `addressee` null speaks to everyone. */
export interface Turn {
  speaker: string;
  addressee: string | null;
  line: string;
  act: string;
  time: number;
}

/** A conversation scene: who talks, at which table (null when standing), and what was said. */
export interface Conversation {
  id: string;
  participants: string[];
  table_id: string | null;
  topic: string;
  turns: Turn[];
  started_at: number;
  /** Game time the next line is due. */
  next_turn_at: number;
  /** The turn a model is writing, if any, and its answer waiting to be spoken. */
  writing: { turn: number; speaker: string; since: number } | null;
  written: { line: string; act: string; addressee: string | null; topic: string } | null;
}

export interface World {
  schema_version: number;
  tick: number;
  time: number;
  paused: boolean;
  speed: number;
  map: {
    width: number;
    height: number;
    tile_size: number;
    blocked: Cell[];
    objects: WorldObject[];
  };
  actors: Actor[];
  departed: Actor[];
  /** Guests yet to arrive, in order of arrival. */
  expected: ExpectedGuest[];
  /** Game seconds after opening when the inn closes; null for an evening that never closes. */
  closes_at: number | null;
  events: WorldEvent[];
  stimuli: Stimulus[];
  next_stimulus_id: number;
  conversations: Conversation[];
  next_conversation_id: number;
}

export interface Snapshot {
  type: "snapshot";
  state: World;
  ai: { mode: Mode; configured?: boolean; model?: string };
  activities: Record<Verb, ActivityView>;
}

export type Command =
  | { type: "pause"; paused: boolean }
  | { type: "speed"; value: number }
  | { type: "refill"; object_id: string; amount: number }
  | { type: "block"; x: number; y: number; blocked: boolean }
  | { type: "force_action"; actor_id: string; action: Action }
  | { type: "save" | "load" | "reset" };
