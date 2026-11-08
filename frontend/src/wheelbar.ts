/** The wheel bar above the hall: the played guest's face and name, a You / Autopilot switch, Pause, and the role sheet. */
import { html, nothing, render } from "lit-html";
import { roleSheet, roleSheetView } from "./rolesheet";
import type { Actor, Command, World } from "./types";
import { wheelState, type WheelState } from "./wheel";

/** Whether a key press is meant for a field the person is typing in (or a control that takes Space itself). */
export function typingTarget(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null;
  return element !== null && typeof element.closest === "function" && element.closest("input, textarea, select, button, [contenteditable]") !== null;
}

export class WheelBar {
  private world: World | null = null;

  constructor(private readonly host: HTMLElement, private readonly send: (command: Command) => void) {
    this.host.className = "wheel";
    this.host.hidden = true;
    window.addEventListener("keydown", (event: KeyboardEvent): void => {
      if (event.code !== "Space" || event.repeat || typingTarget(event.target) || !this.world?.player) return;
      event.preventDefault();
      this.send({ type: "pause", paused: !this.world.paused });
    });
  }

  /** Redraw from the world; the bar hides itself in an evening with no player. */
  apply(world: World): void {
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
      <button class="wheel-pause" @click=${(): void => this.send({ type: "pause", paused: !state.paused })}>${state.paused ? "Resume" : "Pause"} <kbd>Space</kbd></button>
    </div>${actor ? roleSheetView(roleSheet(actor), state.name) : nothing}`, this.host);
  }
}
