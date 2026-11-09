/** The dialogue popup in the middle of the screen: the scene's last lines, whom the line goes to, the input, and the typing pings. */
import { html, nothing, render, type TemplateResult } from "lit-html";
import { chatModel, nextPing, PING_EVERY, sayCommand, type ChatLine, type ChatMember, type ChatModel } from "./chat";
import { CLOSED, dialogueStep, type DialogueEvent, type DialogueState } from "./dialogue";
import type { Command, Snapshot } from "./types";

const MAX_LINE = 200;
/** How many of the scene's lines the popup shows; the speech bubbles show the rest as it happens. */
const SHOWN_LINES = 6;
/** How long after sending an `error` reply still belongs to the line (real ms). */
const REPLY_WINDOW_MS = 3000;

const HEADINGS: Partial<Record<ChatModel["state"], string>> = { on_stage: "On the stage", comeback: "A heckler" };

export class ChatPanel {
  private model: ChatModel | null = null;
  private state: DialogueState = CLOSED;
  private draft: string = "";
  private sent: { text: string; at: number } | null = null;
  private failure: string | null = null;
  private lastPing: number | null = null;
  private focused: boolean = false;

  constructor(private readonly host: HTMLElement, private readonly handlers: { send: (command: Command) => void; more: (id: string) => void }) {
    this.host.className = "dialogue-host";
    window.addEventListener("keydown", (event: KeyboardEvent): void => {
      if (event.key === "Escape" && this.state.open) this.step({ kind: "close" });
    });
  }

  /** Redraw from a snapshot; the popup opens by itself when a scene starts or the player's turn comes. */
  apply(snapshot: Snapshot): void {
    this.model = chatModel(snapshot);
    const turn = snapshot.player_turn;
    if (this.model?.state !== "reading") this.sent = null;
    this.step({ kind: "snapshot", scene: turn?.scene_id ?? null, turn: turn?.state ?? "none", steering: snapshot.state.player?.steering === true });
  }

  /** The IDs of the other members of the played guest's scene: a click on one replies to them. */
  members(): string[] {
    return this.state.scene === null ? [] : (this.model?.members ?? []).map((member: ChatMember): string => member.id);
  }

  /** Open the popup addressed to a member of the scene. */
  replyTo(id: string): void {
    this.step({ kind: "reply", to: id });
  }

  /** Take an `error` reply when it answers the line just sent; false when it is not the chat's. */
  fail(message: string): boolean {
    if (!this.sent || Date.now() - this.sent.at > REPLY_WINDOW_MS) return false;
    this.failure = message;
    this.draft = this.sent.text;
    this.sent = null;
    this.step({ kind: "failed" });
    return true;
  }

  private step(event: DialogueEvent): void {
    const wasOpen: boolean = this.state.open;
    const was: string = this.state.to;
    this.state = dialogueStep(this.state, event);
    this.draw();
    // Opened, or readdressed: the field takes the keys at once.
    if (this.state.open && (!wasOpen || was !== this.state.to)) this.host.querySelector<HTMLInputElement>(".dialogue input")?.focus();
  }

  private submit(): void {
    const command: Command | null = this.model?.enabled ? sayCommand(this.draft, this.state.to) : null;
    if (command === null || command.type !== "say") return;
    this.handlers.send(command);
    this.sent = { text: command.text, at: Date.now() };
    this.draft = "";
    this.failure = null;
    this.step({ kind: "sent" });
  }

  private typed(input: HTMLInputElement): void {
    this.draft = input.value;
    this.failure = null;
    const now: number = Date.now() / 1000;
    if (nextPing(this.lastPing, now, this.draft.trim() !== "", this.focused)) {
      this.lastPing = now;
      this.handlers.send({ type: "typing" });
    }
    this.draw();
  }

  private draw(): void {
    const model: ChatModel | null = this.model;
    if (model === null || !model.enabled && !this.state.open) { render(nothing, this.host); return; }
    if (!this.state.open) { render(this.chip(model), this.host); return; }
    const names: string = model.members.map((member: ChatMember): string => member.name).join(", ");
    const typing: boolean = this.lastPing !== null && Date.now() / 1000 - this.lastPing < 2 * PING_EVERY && this.draft.trim() !== "";
    render(html`<div class="dialogue" role="dialog" aria-label="Talk">
      <header><strong>${HEADINGS[model.state] ?? (names ? `Talking with ${names}` : "Talk")}</strong>
        ${model.secondsLeft !== null ? html`<span class="chat-turn">Your turn · ${Math.ceil(model.secondsLeft)} s${typing ? " · they wait while you type" : ""}</span>` : nothing}
        <button class="dialogue-close" aria-label="Close" title="Close (Esc)" @click=${(): void => this.step({ kind: "close" })}>×</button></header>
      <div class="chat-lines" aria-live="polite">${model.lines.slice(-SHOWN_LINES).map((line: ChatLine): TemplateResult => html`
        <p class=${line.mine ? "chat-line mine" : "chat-line"}><strong>${line.speaker}</strong>${line.addressee ? html` <span class="muted">to ${line.addressee}</span>` : nothing}: ${line.words}${line.reading ? html`<span class=${line.reading.refused ? "chat-reading refused" : "chat-reading"}
          title=${line.reading.refused ? "The world could not read this as meant" : "How the world read it"}>${line.reading.text}</span>` : nothing}</p>`)}
        ${this.sent && model.state === "reading" ? html`<p class="chat-line mine pending">${this.sent.text}</p>` : nothing}</div>
      ${model.picker ? this.picker(model.members) : nothing}
      <div class="chat-input"><input type="text" maxlength=${MAX_LINE} autocomplete="off" aria-label="Say" .value=${this.draft}
        ?disabled=${!model.enabled} placeholder=${model.placeholder}
        @focus=${(): void => { this.focused = true; }} @blur=${(): void => { this.focused = false; }}
        @input=${(event: Event): void => this.typed(event.target as HTMLInputElement)}
        @keydown=${(event: KeyboardEvent): void => { if (event.key === "Enter") { event.preventDefault(); if (!event.shiftKey) this.submit(); } }}>
        <span class="muted chat-count">${this.draft.length}/${MAX_LINE}</span></div>
      ${this.failure ? html`<p class="chat-error" role="alert">${this.failure}</p>` : nothing}
      <p class="muted dialogue-hint">Enter sends · Esc closes · click a guest in the scene to answer them</p></div>`, this.host);
  }

  /** The reminder while the popup is closed in a scene: a click reopens it. */
  private chip(model: ChatModel): TemplateResult {
    const label: string = model.secondsLeft !== null ? `Your turn · ${Math.ceil(model.secondsLeft)} s` : "In a scene · click a guest to answer";
    return html`<button class="dialogue-chip" @click=${(): void => this.step({ kind: "reply", to: this.state.to })}>${label}</button>`;
  }

  private picker(members: ChatMember[]): TemplateResult {
    const choose = (to: string): void => this.step({ kind: "address", to });
    const addressed: ChatMember | undefined = members.find((member: ChatMember): boolean => member.id === this.state.to);
    return html`<div class="chat-faces"><span class="muted">To:</span>
      <button class="chat-to" aria-pressed=${this.state.to === "auto"} @click=${(): void => choose("auto")}>Auto</button>
      <button class="chat-to" aria-pressed=${this.state.to === "everyone"} @click=${(): void => choose("everyone")}>Everyone</button>
      ${members.map((member: ChatMember): TemplateResult => html`<button class="chat-face" aria-pressed=${this.state.to === member.id} title=${member.name}
        @click=${(): void => choose(member.id)}><img src="/characters/${member.face}/Idle/rotations/south.png" alt=${member.name}></button>`)}
      ${addressed ? html`<button class="chat-to more" @click=${(): void => this.handlers.more(addressed.id)}>More with ${addressed.name}…</button>` : nothing}</div>`;
  }
}
