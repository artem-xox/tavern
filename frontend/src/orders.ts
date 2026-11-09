/** What a click means for the played guest: walk, ask what can be done, or inspect; and the rows of the order menu. */
import type { OptionsMessage } from "./commands";
import type { Action, Cell } from "./types";

/** What lies under a click: a free floor cell, a visitor, or an object. */
export type Pick = { kind: "cell"; cell: Cell } | { kind: "visitor"; id: string } | { kind: "object"; id: string };

export type ClickOrder =
  | { kind: "walk"; cell: Cell }
  | { kind: "ask"; target_id: string }
  | { kind: "inspect"; id: string };

/** One row of the order menu; a null action is the "Inspect" row. */
export interface MenuRow {
  label: string;
  action: Action | null;
}

/** The order a click gives; null when it gives none (a floor click while watching). */
export function clickOrder(pick: Pick, steering: boolean): ClickOrder | null {
  if (pick.kind === "cell") return steering ? { kind: "walk", cell: pick.cell } : null;
  return steering ? { kind: "ask", target_id: pick.id } : { kind: "inspect", id: pick.id };
}

/** The action that sends the played guest to a cell. */
export function walkAction(cell: Cell): Action {
  return { id: `walk_to:${cell[0]},${cell[1]}`, verb: "walk_to", target_id: null, cell };
}

/** The menu for an `options` reply: each option as "label · target name", sorted by that text, then "Inspect"; none for an empty reply. */
export function menuRows(reply: OptionsMessage, names: Readonly<Record<string, string>>): MenuRow[] {
  const rows: MenuRow[] = reply.options.map((option): MenuRow => {
    const target: string | null = option.action.target_id;
    return { label: target === null ? option.label : `${option.label} · ${names[target] ?? target}`, action: option.action };
  });
  if (rows.length === 0) return [];
  rows.sort((a: MenuRow, b: MenuRow): number => a.label.localeCompare(b.label));
  return [...rows, { label: "Inspect", action: null }];
}
