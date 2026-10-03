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
  /** `grievances` is derived on the server: the texts of the latest active thoughts that lower the mood. */
  visit: { seconds: number; beers: number; grievances: string[]; left_at?: number };
  thoughts: Thought[];
  /** Base opinion and familiarity per other visitor, before tonight's thoughts. */
  relations: Record<string, { name: string; opinion: number; familiarity: Familiarity }>;
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
export type Familiarity = "stranger" | "acquaintance" | "friend";

/** A timed thought: its mood change, its opinion change toward `about`, and what caused it. */
export interface Thought {
  kind: string;
  about: string | null;
  text: string;
  mood: number;
  opinion: number;
  expires_at: number;
  source_event: string;
}

/** A visitor's inner state as the server derives it for the inspector. */
export interface Mind {
  mood: number;
  /** Active thoughts, oldest first. */
  thoughts: Thought[];
  /** Base opinion plus active thoughts, −100…100, per person they have a relation with. */
  opinions: { id: string; name: string; opinion: number; familiarity: Familiarity }[];
}
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
}

export interface Snapshot {
  type: "snapshot";
  state: World;
  ai: { mode: Mode; configured?: boolean; model?: string };
  activities: Record<Verb, ActivityView>;
  /** Inner state per visitor ID, the departed included. */
  minds: Record<string, Mind>;
}

export type Command =
  | { type: "pause"; paused: boolean }
  | { type: "speed"; value: number }
  | { type: "refill"; object_id: string; amount: number }
  | { type: "block"; x: number; y: number; blocked: boolean }
  | { type: "force_action"; actor_id: string; action: Action }
  | { type: "save" | "load" | "reset" };
