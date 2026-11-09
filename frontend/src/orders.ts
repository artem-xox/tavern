/** What a click means for the played guest: walk, ask what can be done, reply, or inspect; and the rows of the order menu. */
import type { OptionsMessage } from "./commands";
import type { Action, Cell } from "./types";

/** What lies under a click: a free floor cell, a visitor, or an object. */
export type Pick = { kind: "cell"; cell: Cell } | { kind: "visitor"; id: string } | { kind: "object"; id: string };

export type ClickOrder =
  | { kind: "walk"; cell: Cell }
  | { kind: "ask"; target_id: string }
  | { kind: "reply"; to: string }
  | { kind: "inspect"; id: string };

/** One row of the order menu; a null action is the "Inspect" row. */
export interface MenuRow {
  label: string;
  action: Action | null;
}

/**
 * The order a click gives; null when it gives none (a floor click while watching).
 * `how.inspect` (a right or modifier click) inspects as if watching; while steering, a click on one of `how.scene`, the
 * other members of the played guest's scene, replies to them.
 */
export function clickOrder(pick: Pick, steering: boolean, how: { inspect?: boolean; scene?: readonly string[] } = {}): ClickOrder | null {
  if (how.inspect && steering) return clickOrder(pick, false);
  if (steering && pick.kind === "visitor" && how.scene?.includes(pick.id)) return { kind: "reply", to: pick.id };
  if (pick.kind === "cell") return steering ? { kind: "walk", cell: pick.cell } : null;
  return steering ? { kind: "ask", target_id: pick.id } : { kind: "inspect", id: pick.id };
}

/** The action that sends the played guest to a cell. */
export function walkAction(cell: Cell): Action {
  return { id: `walk_to:${cell[0]},${cell[1]}`, verb: "walk_to", target_id: null, cell };
}

/** The menu for an `options` reply: each option as "label · target name", sorted by that text, then "Inspect" unless the target cannot be inspected. */
export function menuRows(reply: OptionsMessage, names: Readonly<Record<string, string>>, inspectable: boolean = true): MenuRow[] {
  const rows: MenuRow[] = reply.options.map((option): MenuRow => {
    const target: string | null = option.action.target_id;
    return { label: target === null ? option.label : `${option.label} · ${names[target] ?? target}`, action: option.action };
  });
  rows.sort((a: MenuRow, b: MenuRow): number => a.label.localeCompare(b.label));
  // A guest can always be inspected, even with nothing to do with them now.
  return inspectable ? [...rows, { label: "Inspect", action: null }] : rows;
}

/** Whether a click only inspects: a right click, or a click with Shift, Alt, Ctrl or Cmd held. */
export function inspectClick(event: { button: number; shiftKey: boolean; altKey: boolean; ctrlKey: boolean; metaKey: boolean }): boolean {
  return event.button === 2 || event.shiftKey || event.altKey || event.ctrlKey || event.metaKey;
}
