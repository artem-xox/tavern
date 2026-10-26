/** Standing on the stage: how far a speaker is raised above the floor, where its footlights burn, and when a number is on. */

/** Pixels a visitor on the stage stands above the floor. */
export const STAGE_LIFT = 8;
/** Pixels a footlight sits in from the stage's front edge and from its ends. */
const FOOTLIGHT_INSET = 5;

/** A stage as the client draws it: its corner cell, its size in cells (one by one in saves from before S2-15), and the way it faces the room. */
export interface StageShape {
  x: number;
  y: number;
  width?: number;
  height?: number;
  facing?: "north" | "south" | "east" | "west";
}

/** Whether a cell lies on the stage. */
function covers(stage: StageShape, cell: { x: number; y: number }): boolean {
  return cell.x >= stage.x && cell.x < stage.x + (stage.width ?? 1) && cell.y >= stage.y && cell.y < stage.y + (stage.height ?? 1);
}

/**
 * How high to draw a visitor above the floor because of the stage under them.
 *
 * @param actor Where the visitor stands, in cells.
 * @param target The object their action targets, if any.
 * @returns `STAGE_LIFT` when the target is a stage and the visitor stands on any of its cells; otherwise 0.
 */
export function stageLift(actor: { x: number; y: number }, target: (StageShape & { kind: string }) | undefined): number {
  return target?.kind === "stage" && covers(target, actor) ? STAGE_LIFT : 0;
}

/**
 * Where the stage's two footlights stand: a candle at each corner of its front edge.
 *
 * @param stage The stage; it faces west unless it says otherwise.
 * @param size Tile size in pixels.
 * @returns The two candles' points in map pixels, `FOOTLIGHT_INSET` in from the front edge and the ends.
 */
export function footlights(stage: StageShape, size: number): { x: number; y: number }[] {
  const left: number = stage.x * size + FOOTLIGHT_INSET;
  const top: number = stage.y * size + FOOTLIGHT_INSET;
  const right: number = (stage.x + (stage.width ?? 1)) * size - FOOTLIGHT_INSET;
  const bottom: number = (stage.y + (stage.height ?? 1)) * size - FOOTLIGHT_INSET;
  const front: Record<NonNullable<StageShape["facing"]>, { x: number; y: number }[]> = {
    west: [{ x: left, y: top }, { x: left, y: bottom }], east: [{ x: right, y: top }, { x: right, y: bottom }],
    north: [{ x: left, y: top }, { x: right, y: top }], south: [{ x: left, y: bottom }, { x: right, y: bottom }],
  };
  return front[stage.facing ?? "west"];
}

/**
 * Whether a number is on: someone up on the stage giving it.
 *
 * @param actors The hall's visitors.
 * @param stage The stage.
 * @returns True while a visitor on the stage's cells is interacting with `give_speech`.
 */
export function performing(actors: readonly { x: number; y: number; status: string; action: { verb: string } | null }[],
                           stage: StageShape): boolean {
  return actors.some((actor): boolean => actor.status === "interacting" && actor.action?.verb === "give_speech" && covers(stage, actor));
}
