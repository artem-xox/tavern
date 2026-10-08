/** Which parts of the map's picture a change in the map redraws. */
import type { World } from "./types";

export type HallMap = World["map"];

/** A fingerprint per part of the picture; a part is redrawn only when its fingerprint changes. */
export interface MapParts {
  /** The canvas size: the hall's cells and the tile size. */
  size: string;
  /** The floor: its walls and everything set into them, and the rugs under the tables. */
  floor: string;
  /** The furniture: what each object looks like where it stands. */
  furniture: string;
}

/**
 * Fingerprint the parts of the map's picture.
 *
 * The server keeps live facts on map objects (the tap's stock, queues, games) that change every few seconds and draw nothing;
 * leaving them out keeps the canvas from being reallocated, which blinks on iOS Safari.
 *
 * @param map The map of a snapshot.
 * @returns One string per part; equal strings mean the part looks the same.
 */
export function mapParts(map: HallMap): MapParts {
  const placed = map.objects.map((object) => [object.id, object.kind, object.x, object.y, object.width ?? 1, object.height ?? 1]);
  return {
    size: JSON.stringify([map.width, map.height, map.tile_size]),
    floor: JSON.stringify([map.width, map.height, map.tile_size, map.blocked, placed]),
    furniture: JSON.stringify([map.tile_size, map.objects.map((object, index) => [placed[index], object.facing ?? null, object.reserved_by])]),
  };
}
