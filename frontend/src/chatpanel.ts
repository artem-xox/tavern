/** The chat docked under the hall: the scene's lines, the "To:" picker, the input, and the typing pings. */
import { html, nothing, render, type TemplateResult } from "lit-html";
import { chatModel, nextPing, sayCommand, type ChatLine, type ChatMember, type ChatModel } from "./chat";
import type { Command, Snapshot } from "./types";

const MAX_LINE = 200;
/** How long after sending an `error` reply still belongs to the line (real ms). */
const REPLY_WINDOW_MS = 3000;

export class ChatPanel {
  private model: ChatModel | null = null;
  private sceneId: string | null = null;
  private to: string = "auto";
  private draft: string = "";
  private sent: { text: string; at: number } | null = null;
  private failure: string | null = null;
  private lastPing: number | null = null;
  private focused: boolean = false;
  private seconds: number = 0;

  constructor(private readonly host: HTMLElement, private readonly send: (command: Command) => void) {
    this.host.className = "chat";
    this.host.hidden = true;
  }

  /** Redraw from a snapshot; the panel hides itself in an evening with no player. */
  apply(snapshot: Snapshot): void {
    this.model = chatModel(snapshot);
    const scene: string | null = snapshot.player_turn?.scene_id ?? null;
    if (scene !== this.sceneId) { this.sceneId = scene; this.to = "auto"; }
    if (this.model?.state !== "reading") this.sent = null;
    this.seconds = snapshot.state.time;
    this.draw();
  }

  /** Take an `error` reply when it answers the line just sent; false when it is not the chat's. */
  fail(message: string): boolean {
    if (!this.sent || Date.now() - this.sent.at > REPLY_WINDOW_MS) return false;
    this.failure = message;
    this.draft = this.sent.text;
    this.sent = null;
    this.draw();
    return true;
  }

  private submit(): void {
    const command: Command | null = this.model?.enabled ? sayCommand(this.draft, this.to) : null;
    if (command === null || command.type !== "say") return;
    this.send(command);
    this.sent = { text: command.text, at: Date.now() };
    this.draft = "";
    this.failure = null;
    this.draw();
  }

  private typed(input: HTMLInputElement): void {
    this.draft = input.value;
    this.failure = null;
    const now: number = Date.now() / 1000;
    if (nextPing(this.lastPing, now, this.draft.trim() !== "", this.focused)) {
      this.lastPing = now;
      this.send({ type: "typing" });
    }
    this.draw();
  }

  private draw(): void {
    const model: ChatModel | null = this.model;
    this.host.hidden = model === null;
    if (model === null) { render(nothing, this.host); return; }
    render(html`<div class="chat-lines" aria-live="polite">${model.lines.slice(-12).map((line: ChatLine): TemplateResult => html`
      <p class=${line.mine ? "chat-line mine" : "chat-line"}><strong>${line.speaker}</strong>${line.addressee ? html` <span class="muted">to ${line.addressee}</span>` : nothing}: ${line.words}</p>`)}
      ${this.sent && model.state === "reading" ? html`<p class="chat-line mine pending">${this.sent.text}</p>` : nothing}</div>
      <div class="chat-faces">${model.picker ? this.picker(model.members) : nothing}
        ${model.secondsLeft !== null ? html`<span class="chat-turn">Your turn · ${Math.ceil(model.secondsLeft)} s</span>` : nothing}</div>
      <div class="chat-input"><input type="text" maxlength=${MAX_LINE} autocomplete="off" aria-label="Say" .value=${this.draft}
        ?disabled=${!model.enabled} placeholder=${model.placeholder}
        @focus=${(): void => { this.focused = true; }} @blur=${(): void => { this.focused = false; }}
        @input=${(event: Event): void => this.typed(event.target as HTMLInputElement)}
        @keydown=${(event: KeyboardEvent): void => { if (event.key === "Enter") { event.preventDefault(); if (!event.shiftKey) this.submit(); } }}>
        <span class="muted chat-count">${this.draft.length}/${MAX_LINE}</span></div>
      ${this.failure ? html`<p class="chat-error" role="alert">${this.failure}</p>` : nothing}`, this.host);
  }

  private picker(members: ChatMember[]): TemplateResult {
    const choose = (to: string): void => { this.to = to; this.draw(); };
    return html`<label>To: <select aria-label="To" @change=${(event: Event): void => choose((event.target as HTMLSelectElement).value)}>
        <option value="auto" ?selected=${this.to === "auto"}>Auto</option><option value="everyone" ?selected=${this.to === "everyone"}>Everyone</option>
        ${members.map((member: ChatMember): TemplateResult => html`<option value=${member.id} ?selected=${this.to === member.id}>${member.name}</option>`)}</select></label>
      ${members.map((member: ChatMember): TemplateResult => html`<button class="chat-face" aria-pressed=${this.to === member.id} title=${member.name}
        @click=${(): void => choose(member.id)}><img src="/characters/${member.face}/Idle/rotations/south.png" alt=${member.name}></button>`)}`;
  }
}
