import { clock } from "./clock";
import { escape } from "./html";
import { renderInspector } from "./inspector";
import type { ActivityView, Actor, Command, Conversation, ItemView, Mind, ServiceHealth, Snapshot, Verb, World, WorldEvent, WorldObject } from "./types";

interface Handlers {
  command: (command: Command) => void;
  select: (id: string) => void;
  edit: (enabled: boolean) => void;
}

function element<T extends HTMLElement>(root: HTMLElement, selector: string): T {
  const match: T | null = root.querySelector<T>(selector);
  if (!match) throw new Error(`Missing UI element: ${selector}`);
  return match;
}

/** Present diagnostics and send controls; world state always comes from snapshots. */
export class Dashboard {
  private world: World | null = null;
  private activities: Record<Verb, ActivityView> = {};
  private items: Record<string, ItemView> = {};
  private minds: Record<string, Mind> = {};
  private intentions = false;
  private verbSignature: string = "";
  private selectedId: string | null = null;
  private connected: boolean = false;
  private editing: boolean = false;
  private targetSignature: string = "";
  private noticeTimer: ReturnType<typeof setTimeout> | undefined;

  constructor(private readonly root: HTMLElement, private readonly handlers: Handlers) {
    this.root.innerHTML = this.layout();
    this.bindControls();
  }

  /** Update the inspector and simulation controls from an authoritative snapshot. */
  apply(snapshot: Snapshot): void {
    this.world = snapshot.state;
    this.activities = snapshot.activities;
    this.items = snapshot.items;
    this.minds = snapshot.minds;
    this.intentions = snapshot.ai.intentions;
    const { state: world, ai } = snapshot;
    this.renderVerbs();
    element(this.root, "#world-time").textContent = clock(world.time);
    element(this.root, "#world-tick").textContent = world.closes_at === null ? `TICK ${world.tick}`
      : world.time >= world.closes_at ? "CLOSED · GUESTS GOING HOME" : `CLOSES AT ${clock(world.closes_at)}`;
    element(this.root, "#pause").textContent = world.paused ? "▶ Resume" : "Ⅱ Pause";
    element<HTMLSelectElement>(this.root, "#speed").value = String(world.speed);
    element(this.root, "#ai-mode").textContent = ai.mode === "jev" ? "Jev configured" : "Local · offline policy";
    element(this.root, "#ai-mode").dataset.mode = ai.mode;
    element(this.root, "#ai-writer").textContent = ai.writer === "haiku" ? "Haiku lines" : "Scripted lines";
    element(this.root, "#ai-writer").dataset.mode = ai.writer === "haiku" ? "jev" : "local";
    element(this.root, "#mode-caption").textContent = ai.mode === "jev" ? `Jev evaluation configured${ai.model ? ` · ${ai.model}` : ""}. Each visitor's decision shows the actual source and any fallback.` : "Offline demo. Decisions use needs and traits; add a TypeSafe key to enable Jev.";
    element(this.root, "#mode-caption").textContent += ai.intentions ? " Claude Haiku writes each guest's intention." : " Intentions offline: no Claude key, so guests have none.";
    this.renderHealth(ai.health);
    this.renderEveningState(world);
    this.renderRoster(world);
    this.renderInspector();
    this.renderEvents(world.events);
    this.updateTargets();
    this.updateControlAvailability();
  }

  /** Show how Jev and Claude are doing: green when usable, amber while unsure or shaky, red when not, grey without a key. */
  private renderHealth(health: Snapshot["ai"]["health"]): void {
    for (const service of ["jev", "claude"] as const) {
      const badge: HTMLElement = element(this.root, `#health-${service}`);
      const report: ServiceHealth | undefined = health?.[service];
      badge.hidden = report === undefined;
      if (!report) continue;
      badge.dataset.health = report.status;
      badge.textContent = `${service.toUpperCase()} ${report.status.replace("_", " ").toUpperCase()}`;
      badge.title = report.reason || `${service} is ${report.status.replace("_", " ")}`;
    }
  }

  /** Show connection state and prevent commands while the server is unavailable. */
  setConnection(connected: boolean, message: string): void {
    this.connected = connected;
    const badge: HTMLElement = element(this.root, "#connection");
    badge.textContent = message;
    badge.dataset.connected = String(connected);
    this.updateControlAvailability();
  }

  /** Select the inspector's visitor without modifying the server. */
  select(id: string | null): void {
    this.selectedId = id;
    this.renderInspector();
    if (this.world) this.renderRoster(this.world);
    this.updateTargets();
    this.updateControlAvailability();
  }

  /** Surface server validation failures and connection problems. */
  showError(message: string): void {
    const notice: HTMLElement = element(this.root, "#notice");
    notice.textContent = message;
    notice.hidden = false;
    clearTimeout(this.noticeTimer);
    this.noticeTimer = setTimeout((): void => { notice.hidden = true; }, 8000);
  }

  /** Display the coordinate or object under the map pointer. */
  hover(message: string): void {
    element(this.root, "#scene-hint").textContent = message;
  }

  private layout(): string {
    return `
      <header class="masthead">
        <div class="brand"><span class="brand-mark" aria-hidden="true">✦</span><div><p class="eyebrow">A PLACE BETWEEN WORLDS</p><h1>The Last Inn</h1></div></div>
        <div class="header-status"><span class="stage-tag">STAGE 0 / TAVERN DEMO</span><span id="connection" class="connection" data-connected="false">Connecting…</span><span class="health-row"><span id="health-jev" class="health-badge" data-health="checking">JEV</span><span id="health-claude" class="health-badge" data-health="checking">CLAUDE</span></span></div>
      </header>
      <div id="notice" class="notice" role="alert" hidden></div>
      <div class="workspace">
        <div class="main-column">
          <section class="scene-card">
            <div class="scene-heading"><div><p class="eyebrow">THE COMMON ROOM</p><h2>Pull up a chair. Stay a while.</h2></div><div class="world-clock"><strong id="world-time">00:00</strong><span id="world-tick">WAITING FOR WORLD</span></div></div>
            <div id="roster" class="roster" aria-label="Select a visitor"></div>
            <div class="game-surround"><div id="game" aria-label="Top-down tavern. Click a visitor to inspect them."></div><div id="curtain" class="curtain" hidden><div class="curtain-card"><p id="curtain-title" class="curtain-title"></p><p id="curtain-text" class="curtain-text"></p><button data-evening data-control class="primary"></button></div></div><div id="loading" class="loading">Waiting for the tavern server<span>Start the backend on port 8000.</span></div></div>
            <div class="scene-footer"><span><i class="legend-dot"></i> Seats · ale · company</span><span id="scene-hint">Click a visitor to inspect their next move.</span></div>
          </section>
          <section class="control-card"><div class="section-heading"><h3>Shape the evening</h3><span class="muted">Change the world. Watch them adapt.</span></div>
            <div class="controls-row"><button id="evening" data-evening data-control class="primary">▶ Start the evening</button><button id="pause" data-control>Ⅱ Pause</button><label class="speed-label">Speed<select id="speed" data-control aria-label="Simulation speed"><option value="0.5">½×</option><option value="1" selected>1×</option><option value="2">2×</option><option value="4">4×</option></select></label><button id="refill" data-control>+ Refill beer</button><button id="edit" data-control aria-pressed="false">Edit obstacles</button></div>
            <p id="edit-hint" class="helper">Refill adds 10 servings. Obstacle mode toggles a clicked cell.</p>
            <div class="controls-row persistence"><button id="save" data-control>Save</button><button id="load" data-control>Load</button><span class="muted">The server keeps your saved world.</span></div>
          </section>
          <section class="events-card"><div class="section-heading"><h3>From the room</h3><span class="muted">Recent world events</span></div><ol id="events" class="event-list"><li class="empty">The evening has yet to begin.</li></ol></section>
        </div>
        <aside class="sidebar"><section class="inspector-card"><div class="section-heading"><h3>Inside a visitor's mind</h3><span class="small-tag">INSPECTOR</span></div><div id="inspector"><p class="empty">Select a visitor in the room.</p></div>
          <div class="force-action"><label for="force-verb">Give this visitor an action</label><div class="force-row"><select id="force-verb" data-control></select><button id="force" data-control>Go →</button></div><select id="force-target" data-control aria-label="Action target"></select><select id="force-item" data-control aria-label="Item to hand over" hidden></select><p class="helper">The server checks the route, availability, and resources.</p></div>
        </section><div class="ai-card"><span id="ai-mode" class="ai-badge">Local · offline policy</span> <span id="ai-writer" class="ai-badge">Scripted lines</span><p id="mode-caption">Waiting for the decision engine.</p></div></aside>
      </div><footer class="page-footer"><span>THE LAST INN <b>✦</b> AN AUTONOMOUS TAVERN</span><span>Observe → decide → walk → act</span></footer>`;
  }

  private bindControls(): void {
    this.root.addEventListener("click", (event: MouseEvent): void => {
      const target: HTMLElement | null = (event.target as HTMLElement).closest("button");
      if (!target) return;
      if (target.dataset.actor) { this.handlers.select(target.dataset.actor); return; }
      if (!this.world) return;
      if (target.dataset.evening !== undefined) this.startOrRestart();
      if (target.id === "pause") this.handlers.command({ type: "pause", paused: !this.world.paused });
      if (["save", "load"].includes(target.id)) this.handlers.command({ type: target.id as "save" | "load" });
      if (target.id === "refill") this.refill();
      if (target.id === "edit") this.toggleEditing();
      if (target.id === "force") this.forceAction();
    });
    element<HTMLSelectElement>(this.root, "#speed").addEventListener("change", (event: Event): void => this.handlers.command({ type: "speed", value: Number((event.target as HTMLSelectElement).value) }));
    element(this.root, "#force-verb").addEventListener("change", (): void => this.updateTargets());
  }

  /** Offer every verb the server runs, keeping the current choice when the list is unchanged. */
  private renderVerbs(): void {
    const signature: string = JSON.stringify(Object.entries(this.activities).map(([verb, activity]: [string, ActivityView]): string[] => [verb, activity.label]));
    if (signature === this.verbSignature) return;
    this.verbSignature = signature;
    const select: HTMLSelectElement = element(this.root, "#force-verb");
    const chosen: string = select.value;
    select.innerHTML = Object.entries(this.activities).map(([verb, activity]: [string, ActivityView]): string => `<option value="${escape(verb)}">${escape(activity.label)}</option>`).join("");
    if (chosen in this.activities) select.value = chosen;
  }

  private renderRoster(world: World): void {
    element(this.root, "#roster").innerHTML = [...world.actors, ...world.departed].map((actor: Actor): string => `<button class="visitor-chip ${actor.id === this.selectedId ? "selected" : ""} ${this.departed(actor) ? "departed" : ""}" data-actor="${escape(actor.id)}" aria-pressed="${actor.id === this.selectedId}"><span class="visitor-dot" style="background:${this.actorColor(actor)}"></span>${escape(actor.name)}<span class="visitor-status">${escape(this.activity(actor))}</span></button>`).join("");
    element(this.root, "#loading").hidden = true;
  }

  /** Offer Start before the first tick and Restart afterwards; frame the room when it is empty. */
  private renderEveningState(world: World): void {
    const waiting: boolean = world.paused && world.tick === 0;
    const over: boolean = world.actors.length === 0 && world.expected.length === 0 && world.departed.length > 0;
    this.root.querySelectorAll<HTMLButtonElement>("[data-evening]").forEach((button: HTMLButtonElement): void => {
      button.textContent = waiting ? "▶ Start the evening" : "↻ Restart the evening";
    });
    element(this.root, "#pause").hidden = waiting;
    element(this.root, "#curtain").hidden = !waiting && !over;
    element(this.root, "#curtain-title").textContent = waiting ? "The guests have just come in" : "The last guest has gone home";
    element(this.root, "#curtain-text").textContent = waiting
      ? `${world.actors.map((actor: Actor): string => actor.name).join(", ")} stand by the door, deciding what they want first.`
      : `${world.departed.reduce((sum: number, actor: Actor): number => sum + actor.visit.beers, 0)} beers poured tonight. Open the doors to a new evening?`;
  }

  private startOrRestart(): void {
    if (!this.world) return;
    // A fresh evening only needs time to start; a running or finished one is replaced.
    if (this.world.paused && this.world.tick === 0) this.handlers.command({ type: "pause", paused: false });
    else this.handlers.command({ type: "reset" });
  }

  private departed(actor: Actor): boolean {
    return this.world?.departed.some((visitor: Actor): boolean => visitor.id === actor.id) ?? false;
  }

  private actorColor(actor: Actor): string {
    // Restrict server color values to CSS colors rather than interpolating arbitrary styles.
    if (typeof actor.color === "number") return `#${actor.color.toString(16).padStart(6, "0")}`;
    return /^#[\da-f]{3,8}$/i.test(actor.color) ? actor.color : "#deb779";
  }

  private renderInspector(): void {
    const actor: Actor | undefined = [...this.world?.actors ?? [], ...this.world?.departed ?? []].find((item: Actor): boolean => item.id === this.selectedId);
    if (!actor || !this.world) return;
    renderInspector(element(this.root, "#inspector"), actor, {
      world: this.world, activities: this.activities, items: this.items, minds: this.minds, intentions: this.intentions,
      departed: this.departed(actor), status: this.activity(actor), color: this.actorColor(actor),
    });
  }

  private renderEvents(events: WorldEvent[]): void {
    element(this.root, "#events").innerHTML = events.length ? events.slice(-8).reverse().map((event: WorldEvent): string => `<li><time>${clock(event.time)}</time><span>${escape(event.message)}</span></li>`).join("") : '<li class="empty">No events yet. Let the visitors settle in.</li>';
  }

  private updateTargets(): void {
    if (!this.world) return;
    const verb: Verb = element<HTMLSelectElement>(this.root, "#force-verb").value as Verb;
    const activity: ActivityView | undefined = this.activities[verb];
    const objects: WorldObject[] = this.world.map.objects.filter((object: WorldObject): boolean => activity?.target_kinds.includes(object.kind) ?? false);
    const targets: { id: string; name: string }[] = activity?.partner ? this.world.actors.filter((actor: Actor): boolean => actor.id !== this.selectedId) : objects;
    const held: string[] = this.heldKinds();
    const signature: string = JSON.stringify([verb, targets.map((object): string[] => [object.id, object.name]), held]);
    const select: HTMLSelectElement = element(this.root, "#force-target");
    select.hidden = !activity?.target_kinds.length && !activity?.partner;
    element(this.root, "#force-item").hidden = !activity?.names_item;
    if (signature === this.targetSignature) return;
    this.targetSignature = signature;
    select.innerHTML = targets.map((object): string => `<option value="${escape(object.id)}">${escape(object.name)}</option>`).join("");
    element(this.root, "#force-item").innerHTML = held.map((kind: string): string => `<option value="${escape(kind)}">${escape(this.items[kind].one)}</option>`).join("");
  }

  /** The kinds of item the selected visitor holds, which are the ones they can hand over. */
  private heldKinds(): string[] {
    const actor: Actor | undefined = this.world?.actors.find((visitor: Actor): boolean => visitor.id === this.selectedId);
    return actor ? Object.keys(actor.inventory).filter((kind: string): boolean => actor.inventory[kind] > 0) : [];
  }

  private activity(actor: Actor): string {
    if (this.departed(actor)) return "gone home";
    const talking: boolean = this.world?.conversations.some((scene: Conversation): boolean => scene.participants.includes(actor.id)) ?? false;
    if (talking && actor.status !== "queued") return "chatting";
    if (actor.status === "walking" || actor.status === "waiting") return actor.status;
    if (actor.status === "queued") return talking ? "chatting in line" : "in line";
    if (actor.action?.verb === "play_darts") return "playing darts";
    if (actor.action?.verb === "watch") return "admiring the view";
    if (actor.seat_id) return actor.action?.verb === "drink" ? "sipping ale" : "seated";
    return actor.status;
  }

  private refill(): void {
    const tap: WorldObject | undefined = this.world?.map.objects.find((object: WorldObject): boolean => object.kind === "tap");
    if (tap) this.handlers.command({ type: "refill", object_id: tap.id, amount: 10 });
  }

  private toggleEditing(): void {
    this.editing = !this.editing;
    const button: HTMLButtonElement = element(this.root, "#edit");
    button.setAttribute("aria-pressed", String(this.editing));
    button.textContent = this.editing ? "✓ Editing obstacles" : "Edit obstacles";
    element(this.root, "#edit-hint").textContent = this.editing ? "Click a floor cell to block it, or an obstacle to unblock it. Server rules still apply." : "Refill adds 10 servings. Obstacle mode toggles a clicked cell.";
    this.handlers.edit(this.editing);
  }

  private forceAction(): void {
    if (!this.selectedId) return;
    const verb: Verb = element<HTMLSelectElement>(this.root, "#force-verb").value as Verb;
    const target: HTMLSelectElement = element(this.root, "#force-target");
    const target_id: string | null = target.hidden ? null : target.value;
    if (!target.hidden && !target_id) { this.showError("No target is available for this action."); return; }
    const itemSelect: HTMLSelectElement = element(this.root, "#force-item");
    if (!itemSelect.hidden && !itemSelect.value) { this.showError("This visitor has nothing to hand over."); return; }
    const item: { item: string } | Record<string, never> = itemSelect.hidden ? {} : { item: itemSelect.value };
    this.handlers.command({ type: "force_action", actor_id: this.selectedId, action: { id: `${verb}:${"item" in item ? `${item.item}:` : ""}${target_id ?? "self"}`, verb, target_id, ...item } });
  }

  private updateControlAvailability(): void {
    this.root.querySelectorAll<HTMLButtonElement | HTMLSelectElement>("[data-control]").forEach((control: HTMLButtonElement | HTMLSelectElement): void => { control.disabled = !this.connected || !this.world; });
    const present: boolean = this.world?.actors.some((actor: Actor): boolean => actor.id === this.selectedId) ?? false;
    element<HTMLButtonElement>(this.root, "#force").disabled = !this.connected || !present;
  }
}
