/** How the inspector words what a guest came to talk for, from the server's aim: a kind, then a colon and a detail. */

/** Words for an aim such as `tell_news:margrave_fever`: underscores become spaces and the detail follows its kind. */
export function aimLabel(aim: string): string {
  const [kind = "", detail] = aim.split(":", 2);
  const words: string = kind.replaceAll("_", " ");
  return detail === undefined ? words : `${words}: ${detail.replaceAll("_", " ")}`;
}
