export type Cell = [number, number];
export type Verb = "take_beer" | "drink" | "rest" | "sit" | "talk" | "play_darts" | "use_toilet" | "inspect" | "wait";
export type Mode = "local" | "jev";

export interface WorldObject {
  id: string;
  kind: "tap" | "toilet" | "chair" | "bar" | "table" | "darts";
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
  x: number;
  y: number;
  traits: Record<string, unknown>;
  needs: { thirst: number; fatigue: number; bladder: number; social: number; boredom: number };
  inventory: { beer: number };
  status: "idle" | "walking" | "interacting" | "waiting";
  action: Action | null;
  seat_id: string | null;
  path: Cell[];
  knowledge: { objects: Record<string, Record<string, unknown>> };
  memory: unknown[];
  decision: { source: Mode; scores: unknown; error: string | null } | null;
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
  events: WorldEvent[];
}

export interface Snapshot {
  type: "snapshot";
  state: World;
  ai: { mode: Mode; configured?: boolean; model?: string };
}

export type Command =
  | { type: "pause"; paused: boolean }
  | { type: "speed"; value: number }
  | { type: "refill"; object_id: string; amount: number }
  | { type: "block"; x: number; y: number; blocked: boolean }
  | { type: "force_action"; actor_id: string; action: Action }
  | { type: "save" | "load" | "reset" };
