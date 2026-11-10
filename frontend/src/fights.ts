/** A fight between two visitors and its swings, as the snapshot carries them. */

/** One swing of a fight: when, who swung, whether it landed, and the health it took. */
export interface Exchange {
  time: number;
  attacker: string;
  hit: boolean;
  damage: number;
}

/** A fight between two (`a` started it); `outcome` is null while it runs. Bystanders may wait a turn against one of them. */
export interface Fight {
  id: string;
  a: string;
  b: string;
  weapons: Record<string, "fists" | "cudgel">;
  started_at: number;
  next_exchange_at: number;
  exchanges: Exchange[];
  waiting: { id: string; against: string }[];
  witnessed: boolean;
  outcome: "knockout" | "double_knockout" | "yielded" | "shouting" | "parted" | "separated" | null;
  loser: string | null;
  ended_at: number | null;
}
