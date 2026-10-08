/** The inspector panel: one visitor's needs, thoughts and decisions, drawn into its container. */
import { html, render, type TemplateResult } from "lit-html";
import { clock } from "./clock";
import type { ActivityView, Actor, Intention, ItemView, Mind, NewsCopy, Thought, Verb, World, WorldObject } from "./types";

/** What the panel needs besides the visitor: the snapshot's tables and the dashboard's wording for this visitor. */
export interface InspectorContext {
  world: World;
  activities: Record<Verb, ActivityView>;
  items: Record<string, ItemView>;
  minds: Record<string, Mind>;
  /** Whether Claude writes intentions (`Snapshot.ai.intentions`). */
  intentions: boolean;
  departed: boolean;
  /** The visitor's status in words, and their colour as a safe CSS value. */
  status: string;
  color: string;
}

const NEED_NAMES: Record<string, string> = { thirst: "Thirst", fatigue: "Fatigue", bladder: "Bladder", social: "Company", boredom: "Boredom" };

/**
 * Draw the inspector for `actor` into `inspector`.
 *
 * lit-html keeps every element the template already made and changes only what differs, so a snapshot every
 * 100 ms never replaces a section or a button under the pointer, and a `<details>` the user opened stays
 * open for every visitor. All sections start closed.
 */
export function renderInspector(inspector: HTMLElement, actor: Actor, ctx: InspectorContext): void {
  const target: WorldObject | undefined = ctx.world.map.objects.find((object: WorldObject): boolean => object.id === actor.action?.target_id);
  const partner: Actor | undefined = ctx.world.actors.find((visitor: Actor): boolean => visitor.id === actor.action?.target_id);
  const action: string = ctx.departed ? "Gone home" : actor.action ? ctx.activities[actor.action.verb]?.label ?? actor.action.verb : actor.seat_id ? "Settled at the table" : "Considering the next move";
  const place: string = actor.visit.left_at !== undefined ? `Left at ${clock(actor.visit.left_at)}` : target ? target.name : partner ? `With ${partner.name}` : "";
  render(html`<div class="visitor-heading"><div class="avatar" style="--visitor:${ctx.color}">${actor.name.slice(0, 1)}</div><div><h2>${actor.name}</h2><span class="status-pill">${ctx.status}</span></div><span class="cell-location">${actor.x}, ${actor.y}</span></div>
    <div class="needs">${needs(actor)}</div>
    <div class="current-action"><span class="eyebrow">CURRENT ACTION</span><strong>${action}</strong><span>${place}${actor.path.length ? ` · ${actor.path.length} steps remaining` : ""}</span></div>
    <div class="inventory-row"><span>Carrying</span><strong>${carrying(actor, ctx)}</strong></div>
    ${visit(actor, ctx)}
    ${intention(actor, ctx)}
    ${mind(actor, ctx)}
    <div class="traits">${Object.entries(actor.traits).map(([key, value]: [string, unknown]) => html`<span>${key.replaceAll("_", " ")}: ${value}</span>`)}</div>
    <details id="decision-detail"><summary>Why this decision? <span class="source-tag">${actor.decision?.source === "jev" ? "JEV" : "LOCAL"}</span></summary><div class="detail-body">${scoreList(actor.decision?.scores)}${actor.decision?.error ? html`<p class="decision-error">Fallback: ${actor.decision.error}</p>` : ""}${seatChoice(actor)}</div></details>
    <details id="knowledge-detail"><summary>What they know <span class="count">${Object.keys(actor.knowledge.objects).length}</span></summary><div class="detail-body">${knowledge(actor)}</div></details>
    <details id="memory-detail"><summary>Recent memories <span class="count">${actor.memory.length}</span></summary><div class="detail-body memories">${memories(actor)}</div></details>`, inspector);
}

function needs(actor: Actor): TemplateResult[] {
  return Object.entries(actor.needs).map(([key, value]: [string, number]): TemplateResult => html`<div class="need"><div><span>${NEED_NAMES[key]}</span><strong>${Math.round(value)}<small>/100</small></strong></div><meter min="0" max="100" value="${value}" aria-label="${NEED_NAMES[key]} urgency" style="--level:${Math.min(100, Math.max(0, value))}%;--need-color:${value > 75 ? "#d7876e" : "#d9b676"}">${Math.round(value)}</meter></div>`);
}

/** List what the guest carries, in the server's wording per kind; nothing when the hands are empty. */
function carrying(actor: Actor, ctx: InspectorContext): string {
  const carried: string[] = Object.entries(actor.inventory).filter(([, count]: [string, number]): boolean => count > 0)
    .map(([kind, count]: [string, number]): string => count === 1 ? ctx.items[kind].one : `${count} ${ctx.items[kind].many}`);
  return carried.join(", ") || "nothing";
}

/** Summarize tonight's visit: time here, beers and own seat. */
function visit(actor: Actor, ctx: InspectorContext): TemplateResult {
  const seat: WorldObject | undefined = ctx.world.map.objects.find((object: WorldObject): boolean => object.id === actor.favorite_seat_id);
  return html`<div class="visit"><div class="inventory-row"><span>Tonight</span><strong>${clock(actor.visit.seconds)} here · ${actor.visit.beers} ${actor.visit.beers === 1 ? "beer" : "beers"}</strong></div>
    <div class="inventory-row"><span>Own seat</span><strong>${seat ? seat.name : "not chosen yet"}</strong></div></div>`;
}

/** Show the guest's current thought and intention, when and why the mind wrote them. */
function intention(actor: Actor, ctx: InspectorContext): TemplateResult {
  const written: Intention | null = actor.intention;
  const goal: string = written?.goal ? `Goal: ${written.goal.kind.replace("_", " ")} ${ctx.world.actors.find((item: Actor): boolean => item.id === written.goal?.target)?.name ?? written.goal.target} (${written.goal.status})` : "";
  const body: TemplateResult = written
    ? html`<p class="helper">“${written.thought}”</p><p class="stage-heading">Intends</p><p>${written.intention}</p>${goal ? html`<p class="helper">${goal}</p>` : ""}<p class="helper">Decided ${Math.max(0, Math.round(ctx.world.time - written.written_at))} s ago, after: ${written.trigger.text}</p>`
    : html`<p class="helper">${ctx.intentions ? "No intention written yet." : "Offline: no Claude key, so guests write no intentions."}</p>`;
  return html`<details id="intention-detail"><summary>Thought and intention</summary><div class="detail-body">${body}</div></details>`;
}

/** List the mood the server derives, the active thoughts behind it, and opinions of others; the section stays when there is nothing yet, so its open state is kept. */
function mind(actor: Actor, ctx: InspectorContext): TemplateResult {
  const state: Mind | undefined = ctx.minds[actor.id];
  const signed = (value: number): string => `${value > 0 ? "+" : ""}${Math.round(value)}`;
  const body: TemplateResult = state ? html`
    <div class="inventory-row"><span>Drink</span><strong>${state.stage} · ${Math.round(state.drunkenness * 100)}%</strong></div>
    ${state.thoughts.length ? html`<ul class="thoughts" aria-label="Thoughts">${state.thoughts.map((thought: Thought) => html`<li class="${thought.mood < 0 ? "bad" : "good"}"><span>${thought.text}</span><strong>${signed(thought.mood)}</strong><small>${Math.max(0, Math.ceil(thought.expires_at - ctx.world.time))} s left</small></li>`)}</ul>` : html`<p class="helper">No thoughts weigh on them.</p>`}
    ${state.opinions.length ? html`<p class="stage-heading">Opinions</p>${state.opinions.map((opinion) => html`<div class="known-object"><span>${opinion.name} · ${opinion.familiarity}</span><span>${signed(opinion.opinion)}</span></div>`)}` : ""}
    ${state.news.length ? html`<p class="stage-heading">News</p>${state.news.map((copy: NewsCopy) => html`<div class="known-object"><span>${copy.topic}${copy.overheard ? " · overheard" : ""} · ${copy.chain.join(" ← ")}</span><span>${Math.round(copy.confidence * 100)}%</span></div><p class="helper">“${copy.told_as}”</p>`)}` : ""}`
    : html`<p class="helper">Nothing to read yet.</p>`;
  return html`<details id="mind-detail"><summary>Mood and thoughts <span class="count">${state ? signed(state.mood) : ""}</span></summary><div class="detail-body">${body}</div></details>`;
}

/** Show the second decision stage: which chair a visitor who decided to sit picked, or which action of a chosen family. */
function seatChoice(actor: Actor): TemplateResult | string {
  const family = actor.decision?.family;
  const stage = actor.decision?.seat ?? family;
  if (!stage) return "";
  const heading: string = family ? `Which ${family.name.replace("_", " ")}?` : "Which seat?";
  return html`<p class="stage-heading">${heading} <span class="source-tag">${stage.source === "jev" ? "JEV" : "LOCAL"}</span></p>${scoreList(stage.scores)}${stage.error ? html`<p class="decision-error">Fallback: ${stage.error}</p>` : ""}`;
}

function scoreList(scores: unknown): TemplateResult {
  if (!scores || typeof scores !== "object" || Object.keys(scores).length === 0) return html`<p class="helper">No decision yet.</p>`;
  const rows: [string, unknown][] = Array.isArray(scores) ? scores.map((score: unknown, index: number): [string, unknown] => [String(index + 1), score]) : Object.entries(scores);
  return html`<div class="score-list">${rows.map(([id, score]: [string, unknown]) => html`<div><span>${id.replaceAll("_", " ")}</span><strong>${typeof score === "number" ? score.toFixed(2) : JSON.stringify(score)}</strong></div>`)}</div>`;
}

function knowledge(actor: Actor): TemplateResult | TemplateResult[] {
  const objects: [string, Record<string, unknown>][] = Object.entries(actor.knowledge.objects);
  if (!objects.length) return html`<p class="helper">Still discovering the room.</p>`;
  return objects.map(([id, known]: [string, Record<string, unknown>]) => html`<div class="known-object"><span>${known.name ?? id}</span><span>${known.kind === "tap" && known.stock !== null && known.stock !== undefined ? `${known.stock} beers observed` : `${known.kind ?? "known"}${known.reserved_by ? " · reserved" : ""}`}</span></div>`);
}

function memories(actor: Actor): TemplateResult | TemplateResult[] {
  if (!actor.memory.length) return html`<p class="helper">No personal memories yet.</p>`;
  return actor.memory.slice(-6).reverse().map((memory: unknown): TemplateResult => {
    if (typeof memory === "string") return html`<p>${memory}</p>`;
    const record: Record<string, unknown> = memory as Record<string, unknown>;
    return html`<p>${record?.message ?? record?.outcome ?? JSON.stringify(memory)}</p>`;
  });
}
