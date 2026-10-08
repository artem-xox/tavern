/** The clock face of a game time. */

/** Format game seconds as `MM:SS`. */
export function clock(time: number): string {
  const minutes: number = Math.floor(time / 60);
  return `${String(minutes).padStart(2, "0")}:${String(Math.floor(time % 60)).padStart(2, "0")}`;
}
