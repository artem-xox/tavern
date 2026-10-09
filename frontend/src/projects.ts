/** How the inspector words a plan a guest is carrying out: the server's project kind, and the step reached. */

/** For example "Plan · settle in, step 2 of 3"; the step is counted from one for the guest, not from zero. */
export function projectLabel(kind: string, step: number, of: number): string {
  return `Plan · ${kind.replaceAll("_", " ")}, step ${Math.min(step + 1, of)} of ${of}`;
}
