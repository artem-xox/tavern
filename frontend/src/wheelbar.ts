/** The wheel bar above the hall: the played guest's face and name, a You / Autopilot switch, Pause, and the role sheet. */
import { html, nothing, render } from "lit-html";
import { roleSheet, roleSheetView } from "./rolesheet";
import type { Actor, Command, PlayerTurn, World } from "./types";
import { wheelState, type WheelState } from "./wheel";

/** Whether a key press is meant for a field the person is typing in (or a control that takes Space itself). */
export function typingTarget(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null;
  return element !== null && typeof element.closest === "function" && element.closest("input, textarea, select, button, [contenteditable]") !== null;
}

export class WheelBar {
  private world: World | null = null;

  constructor(private readonly host: HTMLElement, private readonly send: (command: Command) => void,
              private readonly skip: () => void = (): void => {}) {
    this.host.className = "wheel";
    this.host.hidden = true;
    window.addEventListener("keydown", (event: KeyboardEvent): void => {
      if (event.repeat || typingTarget(event.target) || !this.world?.player) return;
      if (event.code === "KeyF") { event.preventDefault(); this.skip(); return; }
      if (event.code !== "Space") return;
      event.preventDefault();
      this.send({ type: "pause", paused: !this.world.paused });
    });
  }

  /**
   * Redraw from the world; the bar hides itself in an evening with no player.
   *
   * @param turn What the played guest's scene waits for, whether the clock holds still for it (auto-pause), and
   *   whether a skip ahead may start or is running.
   */
  apply(world: World, turn: { state: PlayerTurn["state"] | null; held: boolean; skip?: "can" | "running" | "no" } = { state: null, held: false }): void {
    this.world = world;
    const state: WheelState | null = wheelState(world);
    this.host.hidden = state === null;
    if (state === null) { render(nothing, this.host); return; }
    const actor: Actor | undefined = world.actors.find((item: Actor): boolean => item.id === world.player?.actor_id);
    render(html`<div class="wheel-bar">
      <span class="face"><img src="/characters/${state.face}/Idle/rotations/south.png" alt=""></span>
      <strong>${state.name}</strong><span class="muted">${state.present ? "" : "on the way"}</span>
      <span class="wheel-switch" role="group" aria-label="Who decides">
        <button aria-pressed=${state.steering} @click=${(): void => this.send({ type: "steer", on: true })}>You</button>
        <button aria-pressed=${!state.steering} @click=${(): void => this.send({ type: "steer", on: false })}>Autopilot</button>
      </span>
      ${turn.held ? html`<span class="wheel-held" role="status">The hall waits for your line</span>` : nothing}
      ${state.steering && (turn.state === "your_turn" || turn.state === "comeback") ? html`<button class="wheel-pass" title="Say nothing: the turn passes in silence now" @click=${(): void => this.send({ type: "let_pass" })}>Let it pass</button>` : nothing}
      ${state.steering && turn.skip !== undefined ? html`<button class="wheel-skip" aria-pressed=${turn.skip === "running"} ?disabled=${turn.skip === "no"} title="Run the hall fast until something concerns you" @click=${(): void => this.skip()}>${turn.skip === "running" ? "Skipping…" : "Skip ahead"} <kbd>F</kbd></button>` : nothing}
      <button class="wheel-pause" @click=${(): void => this.send({ type: "pause", paused: !state.paused })}>${state.paused ? "Resume" : "Pause"} <kbd>Space</kbd></button>
    </div>${actor ? roleSheetView(roleSheet(actor), state.name) : nothing}`, this.host);
  }
}
