/** Conversation scenes and what travels through them: turns, invitations, errands, news and a visitor's copy of it. */

/** One spoken line of a conversation scene; `addressee` null speaks to everyone. */
export interface Turn {
  speaker: string;
  addressee: string | null;
  line: string;
  act: string;
  time: number;
  /** The invitation kind an `invite` offers. */
  invitation?: InvitationKind;
  /** The news a `share_news` tells (a key of the speaker's `knowledge.facts`). */
  fact_id?: string;
}

export type InvitationKind = "join_table" | "darts_together" | "dice_together" | "buy_drink" | "leave_together"
  | "move_together";

/** An invitation waiting in a scene for the invitee's answer. */
export interface Invitation {
  kind: InvitationKind;
  from: string;
  to: string;
}

/** An accepted invitation the world is carrying out. */
export interface Errand extends Invitation {
  stage: "accepted" | "fetching" | "carrying" | "following" | "seating";
  /** Ale the inviter held before fetching one for the invitee. */
  held: number;
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
  written: { line: string; act: string; addressee: string | null; topic: string; invitation?: InvitationKind;
    fact_id?: string } | null;
  invitation: Invitation | null;
}

/** A news item of tonight's scenario: the original words, and the guests who start out knowing it. */
export interface News {
  id: string;
  topic: string;
  text: string;
  known_by: string[];
}

/** One visitor's copy of a news item: the words they heard it in, from whom, and how far they believe it. */
export interface Fact {
  topic: string;
  told_as: string;
  /** The visitor who told it; null for a first holder (hops 0). */
  heard_from: string | null;
  heard_at: number;
  /** 0 (not at all) to 1 (sure). */
  confidence: number;
  hops: number;
  /** Caught from a conversation the visitor was not in. */
  overheard: boolean;
}
