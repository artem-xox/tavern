import type { CharacterCard, Tie } from "./characters";
import type { Fight } from "./fights";
import type { CitedEvent, Retelling, Story } from "./story";
import type { Conversation, Errand, Fact, News } from "./talk";

export type Cell = [number, number];
/** The models the server watches. */
export type Service = "jev" | "claude";
/** `checking`: not asked yet; `no_key`, `auth` (key refused), `no_credit`, `unreachable` and `degraded` are failures. */
export type HealthStatus = "checking" | "ok" | "no_key" | "auth" | "no_credit" | "unreachable" | "degraded";
export interface ServiceHealth { status: HealthStatus; reason: string }
/** An action verb; the server's activity table lists the verbs it runs. */
export type Verb = string;
export type Mode = "local" | "jev";
/** Who writes conversation lines: Claude Haiku, or the offline scripted writer. */
export type Writer = "haiku" | "scripted";

/** A game of dice at a dice table: the players in the order they sat down, and when it began and ends (null while one waits). */
export interface DiceGame {
  players: string[];
  since: number;
  ends_at: number | null;
}

export interface WorldObject {
  id: string;
  kind: "tap" | "toilet" | "chair" | "bar" | "table" | "darts" | "door" | "window" | "fireplace" | "dice_table" | "dice_chair" | "stage";
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
  /** The game under way at a dice table; null when none. */
  game?: DiceGame | null;
  /** Cells behind a bar that only staff walk on, and the way its staff look when idle. */
  staff_cells?: Cell[];
  staff_facing?: "north" | "south" | "east" | "west";
  appeal?: number;
  comforts?: string[];
  reach?: number;
}

/** How the server words one kind of item a visitor can carry. */
export interface ItemView {
  one: string;
  many: string;
}

/** How the client names, shows, and targets one verb, as described by the server. */
export interface ActivityView {
  label: string;
  status: string | null;
  pose: string | null;
  target_kinds: WorldObject["kind"][];
  /** Whether it targets another visitor. */
  partner: boolean;
  /** Present, and true, for a verb that also names an item from the visitor's hands. */
  names_item?: boolean;
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

/** The third stage after choosing a social option: what the visitor came to talk for, as an aim ID such as `rematch`. */
export interface AimStage extends DecisionStage {
  name: string;
}

export interface Action {
  id: string;
  verb: Verb;
  target_id: string | null;
  /** The kind of item a verb such as `give` hands over; absent for the others. */
  item?: string;
  /** What a social verb is for (`pass_time`, `tell_news:<fact>`, `invite:<kind>`, ...); absent for the others. */
  aim?: string;
  /** The `[x, y]` cell a `walk_to` action goes to; absent for the others. */
  cell?: [number, number];
}

export interface Actor {
  id: string;
  name: string;
  color: string | number;
  /** Character art under /characters; the scene falls back to the generic visitor. */
  sprite: string;
  /** The ID of the bar they work at, or null for a guest. */
  post: string | null;
  x: number;
  y: number;
  traits: Record<string, unknown>;
  /** The character card a scenario guest was cast from; null for a visitor without one. */
  card: CharacterCard | null;
  /** Starting relationships, from this guest's side. */
  ties: Tie[];
  needs: { thirst: number; fatigue: number; bladder: number; social: number; boredom: number };
  /** Count per item kind (`Snapshot.items`), every kind present, zeros too. */
  inventory: Record<string, number>;
  status: "idle" | "walking" | "interacting" | "waiting" | "queued";
  action: Action | null;
  seat_id: string | null;
  favorite_seat_id: string | null;
  visit: { seconds: number; beers: number; left_at?: number };
  thoughts: Thought[];
  /**
   * Base opinion and familiarity per other visitor, before tonight's thoughts. `name` is what this
   * visitor calls them: their looks until `knows_name`.
   */
  relations: Record<string, { name: string; opinion: number; familiarity: Familiarity; knows_name?: boolean }>;
  /** 0 (sober) to 1 (as drunk as can be); beers raise it and it wears off slowly. */
  drunkenness: number;
  /** Came in unwell, looking pale and feverish, until a remedy cures them. */
  ailing: boolean;
  /** 0 to 100: below 70 they are hurt, and their only business is to mend. */
  health: number;
  /** The state of their body, and until when: down or out they lie on the floor, groggy they are on their feet again. */
  condition: Condition;
  condition_until: number | null;
  path: Cell[];
  knowledge: { objects: Record<string, Record<string, unknown>>; facts: Record<string, Fact> };
  memory: unknown[];
  /** The lines this visitor spoke or heard tonight, oldest first, the newest 40 kept. */
  heard: Heard[];
  decision: (DecisionStage & { seat?: DecisionStage; family?: FamilyStage; aim?: AimStage }) | null;
  /** Where the server turns the visitor; null keeps the seat's, the task's, or the walking direction. */
  facing: Facing | null;
  /** A cell the visitor looks at until a game time, drawn by a stimulus. */
  gaze: { cell: Cell; until: number; stimulus_id: number } | null;
  emote: { kind: EmoteKind; until: number } | null;
  /** Game time of the last interrupt that asked for a fresh decision. */
  interrupted_at: number | null;
  /** What the mind last made of the evening; null before the first one, and always offline. */
  intention: Intention | null;
}

/** A line a visitor spoke or heard; `speaker` is what the visitor called the speaker at that moment. */
export interface Heard {
  time: number;
  scene_id: string;
  speaker_id: string;
  speaker: string;
  line: string;
  act: string;
}

/** A guest's thought and intention, the game time whose situation they answer, and what prompted them. */
export interface Intention {
  thought: string;
  intention: string;
  /** What they set out to do (a kind: `talk_to`, `sit_with`, `treat`, `play_with` or `have_it_out`, about a guest), and whether it is `active`, `done`, `failed` or `expired`; null for none. */
  goal: { kind: string; target: string; status: string } | null;
  /** Index into the card's `obsessions` that this intention serves; absent when it serves none. */
  obsession?: number;
  written_at: number;
  trigger: { kind: string; text: string; time: number };
}

/** The eight ways a visitor can face; a chair or a bar looks only one of the four straight ones. */
export type Facing = "north" | "north-east" | "east" | "south-east" | "south" | "south-west" | "west" | "north-west";
export type Condition = "ok" | "staggered" | "down" | "out" | "groggy";
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
  /** The server's words for the mood, to follow "They are": "in an even mood". */
  mood_words: string;
  /** Active thoughts, oldest first. */
  thoughts: Thought[];
  /** Base opinion plus active thoughts, −100…100, per person they have a relation with. */
  opinions: { id: string; name: string; opinion: number; familiarity: Familiarity }[];
  drunkenness: number;
  stage: "sober" | "tipsy" | "drunk" | "wasted";
  /** How far the scene sways the sprite, 0–1. */
  sway: number;
  /** Copies of the news this visitor carries, by news ID, each with the path it came by. */
  news: NewsCopy[];
}

/** A copy of a news item for the inspector: names, not IDs, and the path back to the start. */
export interface NewsCopy {
  id: string;
  topic: string;
  /** The words the visitor heard it in. */
  told_as: string;
  /** Who told it; null for a first holder. */
  heard_from: string | null;
  hops: number;
  /** 0 (not at all) to 1 (sure). */
  confidence: number;
  overheard: boolean;
  /** Names from this visitor back through each teller, ending in "start". */
  chain: string[];
}
export type EmoteKind = "alert" | "confused" | "angry" | "affection" | "sleep" | "waiting";

/** A scenario guest still on the way, with tonight's needs already drawn. */
export interface ExpectedGuest {
  id: string;
  name: string;
  color: string;
  sprite: string;
  traits: Record<string, number>;
  card?: CharacterCard;
  ties?: Tie[];
  needs: Partial<Actor["needs"]>;
  /** Game seconds after opening. */
  arrives_at: number;
}

export interface WorldEvent {
  time: number;
  actor_id: string | null;
  type: string;
  message: string;
  /** The words a character says aloud, for the `last_call` event, or a `turn` that ended its scene, which the scene shows in a bubble. */
  line?: string;
  /** The action verb, on `action_started` and `action_completed`. */
  verb?: string;
  /** The invitation kind and who made it, on `invitation_accepted`, `_declined` and `_countered`. */
  invitation?: string;
  inviter_id?: string;
  /** The speech act and who it was addressed to (an actor ID, or null for everyone), on `turn`. */
  act?: string;
  addressee?: string | null;
  /** A line the player typed and a person said, on `turn`. */
  player?: boolean;
  /** Whose line failed, on `turn_failed`. */
  speaker_id?: string;
  /** The aim, on `aim_set` and `aim_kept` (a kind, or `kind:detail`). */
  aim?: string;
  /** The goal kind, on `goal_set`. */
  goal?: string;
  /** The index of the obsession an `intention` serves, when it names one. */
  obsession?: number;
  /** The kind of thought answered and the game seconds since it, on `answered`. */
  response?: string;
  after?: number;
  /** The project kind, on the `project_*` events that end one. */
  project?: string;
  /** The listeners who admired and who groaned, on `speech_reaction`. */
  admired?: number;
  groaned?: number;
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

/** What the player's scene waits for: the chat reads it (`player_lines.player_turn`); null where the evening has no player. */
export interface PlayerTurn {
  scene_id: string | null;
  /** none: no scene; free: someone else speaks next; your_turn; reading: the typed line is being read; on_stage; comeback. */
  state: "none" | "free" | "your_turn" | "reading" | "on_stage" | "comeback";
  /** Game time the turn passes in silence; null unless it is the player's turn. */
  silence_at: number | null;
}

/** The person playing tonight: which guest they play, and whether they hold the wheel. */
export interface Player {
  actor_id: string;
  /** True: the player decides for that guest; false: autopilot, the guest's own mind. */
  steering: boolean;
  /** Game time of the last `typing` command; absent or null before the first. */
  typing_at?: number | null;
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
  /** When the barkeep calls closing time, a while before `closes_at`; null for an evening without a call. */
  last_call_at: number | null;
  events: WorldEvent[];
  stimuli: Stimulus[];
  next_stimulus_id: number;
  conversations: Conversation[];
  next_conversation_id: number;
  /** Who the person plays tonight; null for an evening with no player. */
  player: Player | null;
  /** Accepted invitations under way. */
  invitations: Errand[];
  /** Plans under way, at most one per guest. */
  projects: Project[];
  /** Every fight of the evening, those over too. */
  fights: Fight[];
  /** The evening's news as first written; visitors' copies are in their `knowledge.facts`. */
  news: News[];
}

/** A plan a guest is carrying out step by step, without asking for decisions meanwhile. */
export interface Project {
  kind: string;
  /** The guest it belongs to. */
  by: string;
  /** What it is about: a chair, a table or a guest, by kind. */
  target: string;
  /** The guests a plan serves in turn (a round), frozen when it began; absent for other kinds. */
  targets?: string[];
  /** The step reached, from zero, out of `of`. */
  step: number;
  of: number;
  running: boolean;
  started_at: number;
}

export interface Snapshot {
  type: "snapshot";
  state: World;
  /** `intentions`: whether a mind (Claude Haiku) writes guests' intentions; false offline. `health`: how
   *  Jev and Claude are doing (absent where the server does not watch them). */
  ai: { mode: Mode; configured?: boolean; model?: string; writer: Writer; intentions: boolean;
        health?: Record<Service, ServiceHealth> };
  activities: Record<Verb, ActivityView>;
  items: Record<string, ItemView>;
  /** Inner state per visitor ID, the departed included. */
  minds: Record<string, Mind>;
  /** The evening's story score so far. */
  story: Story;
  /** The storyteller's retelling of the evening, once it is over; null until then, and offline. */
  retelling: Retelling | null;
  /** The lines the retelling may cite, by log position (the world's own log is trimmed, so it cannot be used). */
  retelling_events: Record<number, CitedEvent>;
  /** Whether the storyteller is writing the retelling right now. */
  telling: boolean;
  /** What the player's scene waits for; null in an evening with no player. */
  player_turn: PlayerTurn | null;
  /** True while the hall's clock holds still for the person's due line (auto-pause). */
  turn_held: boolean;
}
