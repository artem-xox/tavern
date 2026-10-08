/** The emotes over a guest's head: their pixel pictures, their words, and how they move. */
import { OUTLINE, outlined } from "./pixels.ts";
import type { EmoteKind } from "./types";

export const EMOTE_KINDS: readonly EmoteKind[] = ["alert", "confused", "angry", "affection", "sleep", "waiting"];

/** What each emote means, for the hover line: "Edda · angry". */
export const EMOTE_WORDS: Readonly<Record<EmoteKind, string>> = {
  alert: "startled", confused: "confused", angry: "angry", affection: "fond", sleep: "dozing", waiting: "waiting",
};

const OUTLINE_COLOR = "#1b120d";

interface Art {
  palette: Readonly<Record<string, string>>;
  /** One or more frames of equal size; `.` is transparent. */
  frames: readonly (readonly string[])[];
}

const WAITING_DOTS = ["..............", "..............", "..............", "..............", "..............", ".22...22...22.", ".22...22...22.", "..............", "..............", "..............", "..............", ".............."];

/** The dot at `index` of three is bright (`2`) and the others dim (`4`), so the dots light one after another. */
function waitingFrame(index: number): string[] {
  return WAITING_DOTS.map((row: string): string => [...row].map((cell: string, column: number): string => cell === "2" && Math.floor(column / 5) !== index ? "4" : cell).join(""));
}

const ART: Readonly<Record<EmoteKind, Art>> = {
  alert: { palette: { 2: "#e5483a", 3: "#ff9a7a" }, frames: [[
    "............", "....3222....", "....2222....", "....2222....", ".....22.....", ".....22.....",
    "............", ".....22.....", ".....22.....", "............", "............", "............"]] },
  confused: { palette: { 2: "#4a8fd0", 3: "#9cd0ff" }, frames: [[
    "............", "...322222...", "..22....22..", "..22....22..", "........22..", "......222...",
    ".....22.....", "............", ".....22.....", ".....22.....", "............", "............"]] },
  angry: { palette: { 2: "#e04a3a" }, frames: [[
    "............", "...2....2...", "...2....2...", ".222....222.", "............", "............",
    "............", ".222....222.", "...2....2...", "...2....2...", "............", "............"]] },
  affection: { palette: { 2: "#e0507f", 3: "#ffb0cc" }, frames: [[
    "............", "............", "..222..222..", ".2332222222.", ".2322222222.", ".2222222222.",
    "..22222222..", "...222222...", "....2222....", ".....22.....", "............", "............"]] },
  sleep: { palette: { 2: "#a9bfe8" }, frames: [[
    "............", ".....22222..", "........2...", ".......2....", "......2.....", ".....22222..",
    "............", "..222.......", "....2.......", "...2........", "..222.......", "............"]] },
  waiting: { palette: { 2: "#efdcae", 4: "#8a7c5c" }, frames: [waitingFrame(0), waitingFrame(1), waitingFrame(2)] },
};

/** The pictures of an emote, outlined, one per frame. */
export function emoteFrames(kind: EmoteKind): string[][] {
  return ART[kind].frames.map((frame: readonly string[]): string[] => outlined(frame));
}

/** The palette of an emote's pictures, with the outline's colour. */
export function emotePalette(kind: EmoteKind): Record<string, string> {
  return { ...ART[kind].palette, [OUTLINE]: OUTLINE_COLOR };
}

/** Which picture of an emote to show at `time` milliseconds. */
export function emoteFrame(kind: EmoteKind, time: number): number {
  return kind === "waiting" ? Math.floor(time / 350) % 3 : 0;
}

/** An emote's pop-in lasts this long, in milliseconds; it grows past its size by a fifth, then settles. */
const POP_MS = 200;
const POP_PEAK = 0.6;
const SLEEP_LOOP_MS = 2000;
const SLEEP_RISE = 8;

/**
 * How an emote is drawn `sinceMs` after it appeared, at real time `time`.
 *
 * @returns `scale` (the pop-in), `lift` in whole pixels (a bob of one pixel; a sleeper's z's drift up eight and start over)
 *   and `alpha` (a sleeper's z's fade as they rise).
 */
export function emoteMotion(kind: EmoteKind, sinceMs: number, time: number): { scale: number; lift: number; alpha: number } {
  const t: number = Math.min(sinceMs / POP_MS, 1);
  const scale: number = t < POP_PEAK ? 1.2 * t / POP_PEAK : 1.2 - 0.2 * (t - POP_PEAK) / (1 - POP_PEAK);
  if (kind === "sleep") {
    const phase: number = (time % SLEEP_LOOP_MS) / SLEEP_LOOP_MS;
    return { scale, lift: Math.round(phase * SLEEP_RISE), alpha: 1 - phase ** 2 };
  }
  return { scale, lift: Math.floor(time / 450) % 2, alpha: 1 };
}
