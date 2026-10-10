/** How a fight and its aftermath look: the pose of a fighter or a fallen guest, the motion and the tint, all from the snapshot. */
import type { Condition, Facing } from "./types";

/** Health below which a guest is visibly hurt, and below which battered; the same lines as the server's `wounds`. */
export const HURT = 70;
export const BATTERED = 40;

/** The verbs that put a guest in a fight's stance, and the one that lays them where they fell. */
export const FIGHT_VERBS: readonly string[] = ["start_fight", "join_fight"];

/** What the pose of a guest depends on. */
export interface Body {
  health: number;
  condition: Condition;
  status: string;
  seat_id: string | null;
  action: { verb: string } | null;
}

/**
 * The pose a fight or a wound calls for, or null when the guest looks as they usually do. A fighter is in their
 * stance; a guest on the floor lies; a reeling or groggy or hurt one stands bent, or sits slumped in their chair.
 */
export function fightPose(body: Body): string | null {
  if (body.condition === "out" || body.condition === "down") return "KnockedOut";
  if (body.action && FIGHT_VERBS.includes(body.action.verb)) return "Fighting";
  if (body.condition === "staggered") return "Hurt";
  if (body.condition === "groggy" || body.health < HURT) {
    if (body.status === "walking") return "Hurt";
    return body.seat_id ? "HurtSeated" : "Hurt";
  }
  return null;
}

/** Poses that stand in for one a sprite does not ship yet, in order of preference. */
export const STAND_INS: Readonly<Record<string, readonly string[]>> = {
  Fighting: ["Talking", "Idle"], KnockedOut: ["SleepingSeated", "Seated"], Hurt: ["Idle"], HurtSeated: ["Seated"],
  Shoving: ["Giving", "Idle"], HelpingUp: ["Giving", "Idle"],
};

/** The game time of the last blow that landed on a guest, from the fights' exchanges; null when none has. */
export function lastBlowOn(fights: readonly { a: string; b: string; exchanges: readonly { time: number; attacker: string; hit: boolean }[] }[],
  actorId: string): number | null {
  let latest: number | null = null;
  for (const fight of fights) {
    if (fight.a !== actorId && fight.b !== actorId) continue;
    for (const exchange of fight.exchanges) {
      if (exchange.hit && exchange.attacker !== actorId && (latest === null || exchange.time > latest)) latest = exchange.time;
    }
  }
  return latest;
}

/** The tint of a sprite by health: none while whole, a flush when hurt, deeper when battered (0xffffff is none). */
export function healthTint(health: number): number {
  if (health >= HURT) return 0xffffff;
  return health >= BATTERED ? 0xffd2c8 : 0xff9f94;
}

/** A sprite's offset, in pixels, and tilt, in degrees. */
export interface Motion {
  x: number;
  y: number;
  angle: number;
}

const STEP: Readonly<Record<Facing, readonly [number, number]>> = { north: [0, -1], south: [0, 1], east: [1, 0], west: [-1, 0] };

/**
 * A fighter's motion at `ms`: circling a little, and a lunge of up to 4 pixels toward the opponent that comes round
 * every 1.2 s; the two lunge out of step (`phase`, 0 or 1), so one swings while the other takes it.
 */
export function fightMotion(ms: number, facing: Facing, phase: 0 | 1): Motion {
  const cycle: number = ((ms + phase * 600) % 1200) / 1200;
  const strike: number = cycle < 0.2 ? Math.sin((cycle / 0.2) * Math.PI) : 0;
  const [dx, dy] = STEP[facing];
  return { x: dx * 4 * strike + Math.sin(ms / 130) * 1.2, y: dy * 4 * strike + Math.cos(ms / 170) * 0.8, angle: Math.sin(ms / 90) * 3 };
}

/** The shake of a guest who has just taken a blow, `since` game seconds after it; nothing once it has passed. */
export function blowShake(since: number, ms: number): Motion {
  if (since < 0 || since > 0.5) return { x: 0, y: 0, angle: 0 };
  const fade: number = 1 - since / 0.5;
  return { x: Math.sin(ms / 20) * 3 * fade, y: 0, angle: Math.sin(ms / 25) * 8 * fade };
}

/** How red the flash of a blow still is, 0 to 1, `since` game seconds after it. */
export function blowFlash(since: number): number {
  return since < 0 || since > 0.4 ? 0 : 1 - since / 0.4;
}

/** A hurt guest's walk: a bob of a pixel or two, slowed, so they limp. */
export function limp(ms: number): number {
  return Math.abs(Math.sin(ms / 260)) * -3;
}

/** The three stars of a groggy guest, circling over the head: offsets from the head's centre at `ms`. */
export function starsOrbit(ms: number): { x: number; y: number }[] {
  return [0, 1, 2].map((index: number): { x: number; y: number } => {
    const angle: number = ms / 420 + (index * 2 * Math.PI) / 3;
    return { x: Math.cos(angle) * 14, y: Math.sin(angle) * 4 };
  });
}

/** Where a cudgel sits in a hand, in pixels from the figure's centre, how it is tilted, and whether the body hides it. */
export interface Hand {
  x: number;
  y: number;
  angle: number;
  behind: boolean;
}

const HANDS: Readonly<Record<Facing, Hand>> = {
  south: { x: 17, y: -8, angle: 25, behind: false },
  north: { x: -17, y: -8, angle: -25, behind: true },
  east: { x: 18, y: -9, angle: 35, behind: false },
  west: { x: -18, y: -9, angle: -35, behind: false },
};

/** Where the cudgel of a guest who holds one is drawn, by the way they face; raised higher in a fighter's stance. */
export function cudgelHand(facing: Facing, fighting: boolean): Hand {
  const hand: Hand = HANDS[facing];
  return fighting ? { ...hand, y: hand.y - 7, angle: hand.angle * 2 } : hand;
}

/** Whether a pose shows a held cudgel: a guest lying down, asleep or on the toilet does not hold it out. */
export function showsCudgel(pose: string): boolean {
  return !["KnockedOut", "SleepingSeated", "Bathroom"].includes(pose);
}
