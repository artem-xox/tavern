/** The faint haze over a drunk guest: a slow amber glow at their feet and beer bubbles drifting up past their head. */
import type { Mind } from "./types.ts";

/** The haze's bounds, in the guest's own coordinates (their feet are near 0, their head near −50). */
export const AURA_TOP = -70;
export const AURA_BOTTOM = 10;

/** One bubble of the haze: where it is, how big, and how faint. */
export interface Mote {
  x: number;
  y: number;
  radius: number;
  alpha: number;
}

/** What to draw over a guest this frame: the glow's opacity (0 for none) and the bubbles. */
export interface Haze {
  glow: number;
  motes: Mote[];
}

/** Per stage: how many bubbles, how bright the brightest is, and the glow's resting opacity and swell. */
const STAGES: Partial<Record<Mind["stage"], { motes: number; alpha: number; glow: number; swell: number }>> = {
  drunk: { motes: 3, alpha: 0.4, glow: 0.1, swell: 0.04 },
  wasted: { motes: 5, alpha: 0.55, glow: 0.17, swell: 0.06 },
};
/** A bubble rises from the chest to above the head in this many milliseconds; the glow breathes slower. */
const RISE_MS = 2400;
const GLOW_MS = 700;
const RISE_FROM = -20;
const RISE_TO = -62;

/**
 * The haze over a guest at a stage of drink, at a moment.
 *
 * @param stage The guest's stage of drink, as the server names it; sober and tipsy guests have none.
 * @param time Real time in milliseconds.
 * @param phase 0–1, the guest's own offset, so that two drunks do not bob in step.
 * @returns The glow and the bubbles, each bubble fading in at the chest and out above the head.
 */
export function aura(stage: Mind["stage"], time: number, phase: number): Haze {
  const look = STAGES[stage];
  if (!look) return { glow: 0, motes: [] };
  const motes: Mote[] = [];
  for (let index: number = 0; index < look.motes; index += 1) {
    const rise: number = (((time / RISE_MS + phase + index / look.motes) % 1) + 1) % 1;
    // Bubbles alternate sides of the head, and each wanders a little as it rises.
    const side: number = (index % 2 === 0 ? -1 : 1) * (11 + 3 * (index % 3));
    motes.push({ x: side + 3 * Math.sin(rise * 4 * Math.PI + index), y: RISE_FROM + (RISE_TO - RISE_FROM) * rise,
      radius: 1.5 + (index % 2), alpha: look.alpha * Math.sin(Math.PI * rise) });
  }
  return { glow: look.glow + look.swell * Math.sin(time / GLOW_MS + phase * 2 * Math.PI), motes };
}

/**
 * A guest's own offset for the haze, steady across frames.
 *
 * @param id The guest's ID.
 * @returns 0–1, from a hash of the ID.
 */
export function auraPhase(id: string): number {
  let hash: number = 0;
  for (const char of id) hash = (hash * 31 + char.charCodeAt(0)) % 1000;
  return hash / 1000;
}
