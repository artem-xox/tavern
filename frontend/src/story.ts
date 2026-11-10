/** The story the evening makes: its score, the retelling's chapters, and the log lines they cite. */

/** The server's story score: moments counted per kind, and their weighted total. */
export interface Story {
  moments: Record<string, number>;
  score: number;
}

/** One chapter of a retelling: its text, the log positions it cites, and the IDs of the guests who did those things. */
export interface Chapter {
  text: string;
  events: number[];
  actors: string[];
}

/** An evening retold: a catchy title and a few cited chapters. */
export interface Retelling {
  title: string;
  chapters: Chapter[];
}

/** What the client knows of a log line a chapter cites, by its position: what it was, who did it, and whether the player typed it. */
export interface CitedEvent {
  type: string;
  actor_id: string | null;
  player: boolean;
}
