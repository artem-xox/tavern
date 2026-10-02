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
  status: "idle" | "walking" | "interacting" | "waiting";
  action: Action | null;
  seat_id: string | null;
  favorite_seat_id: string | null;
  visit: { seconds: number; beers: number; grievances: string[]; left_at?: number };
  path: Cell[];
  knowledge: { objects: Record<string, Record<string, unknown>> };
  memory: unknown[];
  decision: (DecisionStage & { seat?: DecisionStage; family?: FamilyStage }) | null;
}

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
