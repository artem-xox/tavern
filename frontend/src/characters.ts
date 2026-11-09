/** The character catalog and cards the server describes: who a guest is, how they look, their casts and ties. */

/** Who a guest is in words, plus the 0–1 params the rules read. */
export interface CharacterCard {
  id: string;
  name: string;
  sprite: string;
  occupation: string;
  background: string;
  temperament: string;
  speech: string;
  quirks: string;
  goal: string;
  params: Record<string, number>;
  /** How strangers see the guest until they learn the name. */
  looks?: string;
  /** What a famous guest cannot leave alone tonight, up to three; an intention's `obsession` indexes it. */
  obsessions?: string[];
  /** Lines the guest is known for; the first closes a number on the stage. */
  catchphrases?: string[];
  /** Counts only in how much punishment a fighter takes. */
  sex?: "female" | "male";
}

/** Public rendering data returned by the server's character catalog. */
export interface CharacterVisuals {
  size: number;
  lift: number;
  poses: string[];
}

export interface PublicCharacter {
  id: string;
  role: "guest" | "bartender";
  /** The folder the character lives in: locals, famous guests, or the bar's staff. */
  cast: "locals" | "guests" | "staff";
  name: string;
  color: string;
  sprite: string;
  visuals: CharacterVisuals;
}

export interface CharacterCatalog {
  characters: PublicCharacter[];
}

/** A guest's face on the start screen: the name and the card's occupation. */
export interface CastMember {
  id: string;
  name: string;
  description: string;
}

/** A cast the player can pick the evening's guests from (`/api/casts`). */
export interface Cast {
  id: string;
  title: string;
  characters: CastMember[];
}

/** A starting relationship as one guest holds it. */
export interface Tie {
  with: string;
  name: string;
  kind: "old friends" | "rivals" | "bad blood";
  note: string;
}
