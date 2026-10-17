import { html, nothing, render, type TemplateResult } from "lit-html";
import { canStart, DEFAULT_MINUTES, MAX_GUESTS, MINUTE_CHOICES, startCommand, togglePick } from "./lineup";
import type { Cast, Command } from "./types";

/** The start screen: choose a cast, click up to six faces, choose the length, and open the evening. */
export class LineupScreen {
  private cast: Cast | null = null;
  private picked: string[] = [];
  private minutes: number = DEFAULT_MINUTES;
  private resumable = false;

  constructor(private readonly host: HTMLElement, private readonly casts: readonly Cast[], private readonly send: (command: Command) => void) {
    this.host.className = "lineup-window";
    this.host.setAttribute("role", "dialog");
    this.host.setAttribute("aria-modal", "true");
    this.host.setAttribute("aria-labelledby", "lineup-heading");
    this.host.hidden = true;
  }

  /** Show the screen from its first step; `resumable` offers a way back to an evening already under way. */
  open(resumable: boolean): void {
    this.cast = null;
    this.picked = [];
    this.resumable = resumable;
    this.host.hidden = false;
    this.draw();
  }

  close(): void {
    this.host.hidden = true;
  }

  private draw(): void {
    render(html`<div class="lineup-card">
      <h2 id="lineup-heading">${this.cast ? `Who is drinking tonight? · ${this.cast.title}` : "Who walks into the Story Tavern?"}</h2>
      ${this.cast ? this.faces(this.cast) : this.choices()}
      ${this.resumable ? html`<button class="link" @click=${(): void => this.close()}>Back to the evening</button>` : nothing}
    </div>`, this.host);
  }

  private choices(): TemplateResult {
    return html`<div class="cast-choices">${this.casts.map((cast: Cast) => html`<button class="cast-choice" @click=${(): void => { this.cast = cast; this.draw(); }}><strong>${cast.title}</strong><span>${cast.characters.length} to choose from</span></button>`)}</div>`;
  }

  private faces(cast: Cast): TemplateResult {
    return html`<div class="faces">${cast.characters.map((person) => html`<button class="face ${this.picked.includes(person.id) ? "picked" : ""}" aria-pressed=${this.picked.includes(person.id)} @click=${(): void => { this.picked = togglePick(this.picked, person.id); this.draw(); }}>
        <img src="/characters/${person.id}/Idle/rotations/south.png" alt="" width="68" height="68"><strong>${person.name}</strong><span>${person.description}</span></button>`)}</div>
      <div class="lineup-actions">
        <button @click=${(): void => { this.cast = null; this.picked = []; this.draw(); }}>← Casts</button>
        <span class="muted">${this.picked.length} of ${MAX_GUESTS} picked</span>
        <label>Evening <select @change=${(event: Event): void => { this.minutes = Number((event.target as HTMLSelectElement).value); }}>${MINUTE_CHOICES.map((minutes: number) => html`<option value=${minutes} ?selected=${minutes === this.minutes}>${minutes} min</option>`)}</select></label>
        <button class="primary" ?disabled=${!canStart(this.picked)} @click=${(): void => this.start(cast)}>▶ Open the doors</button>
      </div>`;
  }

  private start(cast: Cast): void {
    this.send(startCommand(cast.id, this.picked, this.minutes));
    this.close();
  }
}
