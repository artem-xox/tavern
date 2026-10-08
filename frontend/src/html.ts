/** Making text safe to put into an HTML string. */

/** Escape the characters that would start markup or end an attribute. */
export function escape(value: unknown): string {
  return String(value).replace(/[&<>"']/g, (character: string): string => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]!);
}
