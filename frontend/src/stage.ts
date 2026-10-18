/** Standing on the stage: how far a speaker is raised above the floor. */

/** Pixels a visitor on the stage stands above the floor. */
export const STAGE_LIFT = 8;

/**
 * How high to draw a visitor above the floor because of the stage under them.
 *
 * @param actor Where the visitor stands, in cells.
 * @param target The object their action targets, if any.
 * @returns `STAGE_LIFT` when the target is a stage and the visitor stands on its cell; otherwise 0.
 */
export function stageLift(actor: { x: number; y: number }, target: { kind: string; x: number; y: number } | undefined): number {
  return target?.kind === "stage" && target.x === actor.x && target.y === actor.y ? STAGE_LIFT : 0;
}
