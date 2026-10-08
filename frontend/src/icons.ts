/** Pictures of what a visitor carries, drawn from 16 × 16 pixel maps and keyed by item kind, never by guest. */
import { OUTLINE, outlined } from "./pixels.ts";

const OUTLINE_COLOR = "#1b120d";

interface Icon {
  palette: Readonly<Record<string, string>>;
  rows: readonly string[];
}

const ICONS: Readonly<Record<string, Icon>> = {
  beer: { palette: { 1: "#fbf1d9", 2: "#e2cfa3", 3: "#c88a3a", 4: "#e8b45f", 5: "#7a5230", 6: "#a8743f" }, rows: [
    "................", "....1..11.......", "...11111111.....", "..1111112111....", "...2222222.1....", "...4333333......",
    "...5555555......", "...4333333.66...", "...4333333..6...", "...4333333..6...", "...4333333.66...", "...5555555......",
    "...4333333......", "................", "................", "................"] },
  remedy: { palette: { 1: "#8a5a2b", 2: "#b07a44", 3: "#d8eee6", 4: "#9cc7b8", 5: "#4f9a5a", 6: "#7cc46e", 7: "#2f6b3a" }, rows: [
    "................", "................", ".......21.......", ".......11.......", ".......34.......", "......3444......",
    ".....344444.....", "....36666666....", "....36555555....", "....65555557....", "....65555557....", ".....555577.....",
    "......5777......", "................", "................", "................"] },
  keepsake: { palette: { 1: "#e6c25c", 2: "#fff0b0", 3: "#a87a26", 4: "#c2457a", 5: "#f29bc0", 6: "#c9a64a" }, rows: [
    "................", ".....666666.....", "....6......6....", "...6........6...", "...6........6...", "....6......6....",
    ".....6....6.....", "......6..6......", ".......11.......", "......2111......", ".....211111.....", "....21154113....",
    "....21144113....", ".....111113.....", "......1333......", "................"] },
};

/** What a kind without a picture of its own looks like: a tied bundle. */
const BUNDLE: Icon = { palette: { 1: "#b08a5a", 2: "#d9b98a", 3: "#7a5a36", 4: "#c0392b" }, rows: [
  "................", "................", "......2..1......", ".......44.......", "......1441......", ".....211113.....",
  "....22111113....", "....21111113....", "....21111113....", "....11111133....", ".....111333.....", "................",
  "................", "................", "................", "................"] };

/** The pixels of an item's picture: coloured cells on a square grid, with a dark outline ringing the art. */
export interface IconPixels {
  size: number;
  pixels: { x: number; y: number; color: string }[];
}

/**
 * The picture of an item kind, outlined so it reads on any slot.
 *
 * @param kind The inventory key (`beer`, `remedy`, `keepsake`); a kind with no picture gets the bundle.
 * @returns The grid size (the map plus its outline) and every coloured cell.
 */
export function iconPixels(kind: string): IconPixels {
  const icon: Icon = Object.hasOwn(ICONS, kind) ? ICONS[kind]! : BUNDLE;
  const rows: string[] = outlined(icon.rows);
  const colors: Record<string, string> = { ...icon.palette, [OUTLINE]: OUTLINE_COLOR };
  return {
    size: rows.length,
    pixels: rows.flatMap((row: string, y: number) => [...row].flatMap((key: string, x: number) => key === "." ? [] : [{ x, y, color: colors[key]! }])),
  };
}
