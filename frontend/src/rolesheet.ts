/** The played guest's cheat sheet: what the card says about who they are, what they want and whom they dislike. */
import { html, nothing, type TemplateResult } from "lit-html";
import type { Actor } from "./types";

/** A rival with the reason, in words, when the tie gives one. */
export interface Rival {
  name: string;
  why: string;
}

export interface RoleSheet {
  /** Labelled lines of who the guest is. */
  persona: (readonly [string, string])[];
  obsessions: string[];
  catchphrases: string[];
  rivals: Rival[];
}

const PERSONA: readonly (readonly [string, "occupation" | "temperament" | "speech" | "quirks"])[] = [
  ["Who", "occupation"], ["Temper", "temperament"], ["Speech", "speech"], ["Quirks", "quirks"],
];
const RIVAL_KINDS: readonly string[] = ["rivals", "bad blood"];

/** The sheet for a guest: nothing is checked or scored, and a guest without a card or ties has empty lists. */
export function roleSheet(actor: Actor): RoleSheet {
  const card = actor.card;
  const rivals: (Rival & { id: string })[] = actor.ties.filter((tie) => RIVAL_KINDS.includes(tie.kind)).map((tie) => ({ id: tie.with, name: tie.name, why: tie.note }));
  const listed: Set<string> = new Set(rivals.map((rival) => rival.id));
  for (const [id, relation] of Object.entries(actor.relations)) {
    if (relation.opinion < 0 && !listed.has(id)) rivals.push({ id, name: relation.name, why: "" });
  }
  return {
    persona: card ? PERSONA.filter(([, key]) => card[key]).map(([label, key]) => [label, card[key]] as const) : [],
    obsessions: card?.obsessions ?? [],
    catchphrases: card?.catchphrases ?? [],
    rivals: rivals.map(({ name, why }) => ({ name, why })),
  };
}

/** The sheet as a foldable panel; empty sections are left out. */
export function roleSheetView(sheet: RoleSheet, name: string): TemplateResult {
  const list = (title: string, items: readonly string[]): TemplateResult | typeof nothing =>
    items.length === 0 ? nothing : html`<h4>${title}</h4><ul>${items.map((item) => html`<li>${item}</li>`)}</ul>`;
  return html`<details class="role-sheet"><summary>Your role · ${name}</summary>
    ${sheet.persona.length === 0 ? nothing : html`<dl>${sheet.persona.map(([label, text]) => html`<dt>${label}</dt><dd>${text}</dd>`)}</dl>`}
    ${list("Obsessions", sheet.obsessions)}${list("Catchphrases", sheet.catchphrases)}
    ${sheet.rivals.length === 0 ? nothing : html`<h4>Rivals</h4><ul>${sheet.rivals.map((rival) => html`<li><strong>${rival.name}</strong>${rival.why ? html` · ${rival.why}` : nothing}</li>`)}</ul>`}
  </details>`;
}
