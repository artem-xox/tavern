/** The inspector panel: one visitor's needs, thoughts and decisions, written into its container. */
import { clock } from "./clock";
import { escape } from "./html";
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

/** Write the inspector for `actor` into `inspector`, keeping the sections the user has opened. */
export function renderInspector(inspector: HTMLElement, actor: Actor, ctx: InspectorContext): void {
  const openDetails: Set<string> = new Set(Array.from(inspector.querySelectorAll<HTMLDetailsElement>("details[open]")).map((detail: HTMLDetailsElement): string => detail.id));
  const sameActor: boolean = inspector.dataset.actor === actor.id;
  inspector.dataset.actor = actor.id;
  const target: WorldObject | undefined = ctx.world.map.objects.find((object: WorldObject): boolean => object.id === actor.action?.target_id);
  const partner: Actor | undefined = ctx.world.actors.find((visitor: Actor): boolean => visitor.id === actor.action?.target_id);
  inspector.innerHTML = `<div class="visitor-heading"><div class="avatar" style="--visitor:${ctx.color}">${escape(actor.name.slice(0, 1))}</div><div><h2>${escape(actor.name)}</h2><span class="status-pill">${escape(ctx.status)}</span></div><span class="cell-location">${actor.x}, ${actor.y}</span></div>
    <div class="needs">${needs(actor)}</div>
    <div class="current-action"><span class="eyebrow">CURRENT ACTION</span><strong>${ctx.departed ? "Gone home" : actor.action ? escape(ctx.activities[actor.action.verb]?.label ?? actor.action.verb) : actor.seat_id ? "Settled at the table" : "Considering the next move"}</strong><span>${actor.visit.left_at !== undefined ? `Left at ${clock(actor.visit.left_at)}` : target ? escape(target.name) : partner ? `With ${escape(partner.name)}` : ""}${actor.path.length ? ` · ${actor.path.length} steps remaining` : ""}</span></div>
    <div class="inventory-row"><span>Carrying</span><strong>${carrying(actor, ctx)}</strong></div>
    ${visit(actor, ctx)}
    ${intention(actor, ctx)}
    ${mind(actor, ctx)}
    <div class="traits">${Object.entries(actor.traits).map(([key, value]: [string, unknown]): string => `<span>${escape(key.replaceAll("_", " "))}: ${escape(value)}</span>`).join("")}</div>
    <details id="decision-detail" open><summary>Why this decision? <span class="source-tag">${actor.decision?.source === "jev" ? "JEV" : "LOCAL"}</span></summary><div class="detail-body">${scoreList(actor.decision?.scores)}${actor.decision?.error ? `<p class="decision-error">Fallback: ${escape(actor.decision.error)}</p>` : ""}${seatChoice(actor)}</div></details>
    <details id="knowledge-detail" open><summary>What they know <span class="count">${Object.keys(actor.knowledge.objects).length}</span></summary><div class="detail-body">${knowledge(actor)}</div></details>
    <details id="memory-detail"><summary>Recent memories <span class="count">${actor.memory.length}</span></summary><div class="detail-body memories">${memories(actor)}</div></details>`;
  if (sameActor) inspector.querySelectorAll<HTMLDetailsElement>("details").forEach((detail: HTMLDetailsElement): void => { detail.open = openDetails.has(detail.id); });
}

function needs(actor: Actor): string {
  const names: Record<string, string> = { thirst: "Thirst", fatigue: "Fatigue", bladder: "Bladder", social: "Company", boredom: "Boredom" };
  return Object.entries(actor.needs).map(([key, value]: [string, number]): string => `<div class="need"><div><span>${names[key]}</span><strong>${Math.round(value)}<small>/100</small></strong></div><meter min="0" max="100" value="${value}" aria-label="${names[key]} urgency" style="--level:${Math.min(100, Math.max(0, value))}%;--need-color:${value > 75 ? "#d7876e" : "#d9b676"}">${Math.round(value)}</meter></div>`).join("");
}

/** List what the guest carries, in the server's wording per kind; nothing when the hands are empty. */
function carrying(actor: Actor, ctx: InspectorContext): string {
  const carried: string[] = Object.entries(actor.inventory).filter(([, count]: [string, number]): boolean => count > 0)
    .map(([kind, count]: [string, number]): string => count === 1 ? ctx.items[kind].one : `${count} ${ctx.items[kind].many}`);
  return escape(carried.join(", ") || "nothing");
}

/** Summarize tonight's visit: time here, beers and own seat. */
function visit(actor: Actor, ctx: InspectorContext): string {
  const seat: WorldObject | undefined = ctx.world.map.objects.find((object: WorldObject): boolean => object.id === actor.favorite_seat_id);
  return `<div class="visit"><div class="inventory-row"><span>Tonight</span><strong>${clock(actor.visit.seconds)} here · ${actor.visit.beers} ${actor.visit.beers === 1 ? "beer" : "beers"}</strong></div>
    <div class="inventory-row"><span>Own seat</span><strong>${seat ? escape(seat.name) : "not chosen yet"}</strong></div></div>`;
}

/** Show the guest's current thought and intention, when and why the mind wrote them. */
function intention(actor: Actor, ctx: InspectorContext): string {
  const intention: Intention | null = actor.intention;
  const body: string = intention
    ? `<p class="helper">“${escape(intention.thought)}”</p><p class="stage-heading">Intends</p><p>${escape(intention.intention)}</p>${intention.goal ? `<p class="helper">Goal: ${escape(intention.goal.kind.replace("_", " "))} ${escape(ctx.world.actors.find((item) => item.id === intention.goal?.target)?.name ?? intention.goal.target)} (${escape(intention.goal.status)})</p>` : ""}<p class="helper">Decided ${Math.max(0, Math.round((ctx.world.time ?? 0) - intention.written_at))} s ago, after: ${escape(intention.trigger.text)}</p>`
    : `<p class="helper">${ctx.intentions ? "No intention written yet." : "Offline: no Claude key, so guests write no intentions."}</p>`;
  return `<details id="intention-detail" open><summary>Thought and intention</summary><div class="detail-body">${body}</div></details>`;
}

/** List the mood the server derives, the active thoughts behind it, and opinions of others. */
function mind(actor: Actor, ctx: InspectorContext): string {
  const mind: Mind | undefined = ctx.minds[actor.id];
  if (!mind) return "";
  const signed = (value: number): string => `${value > 0 ? "+" : ""}${Math.round(value)}`;
  const thoughts: string = mind.thoughts.map((thought: Thought): string => `<li class="${thought.mood < 0 ? "bad" : "good"}"><span>${escape(thought.text)}</span><strong>${signed(thought.mood)}</strong><small>${Math.max(0, Math.ceil(thought.expires_at - (ctx.world.time ?? 0)))} s left</small></li>`).join("");
  const opinions: string = mind.opinions.map((opinion): string => `<div class="known-object"><span>${escape(opinion.name)} · ${escape(opinion.familiarity)}</span><span>${signed(opinion.opinion)}</span></div>`).join("");
  const news: string = mind.news.map((copy: NewsCopy): string => `<div class="known-object"><span>${escape(copy.topic)}${copy.overheard ? " · overheard" : ""} · ${escape(copy.chain.join(" ← "))}</span><span>${Math.round(copy.confidence * 100)}%</span></div><p class="helper">“${escape(copy.told_as)}”</p>`).join("");
  return `<details id="mind-detail" open><summary>Mood and thoughts <span class="count">${signed(mind.mood)}</span></summary><div class="detail-body">
    <div class="inventory-row"><span>Drink</span><strong>${escape(mind.stage)} · ${Math.round(mind.drunkenness * 100)}%</strong></div>
    ${thoughts ? `<ul class="thoughts" aria-label="Thoughts">${thoughts}</ul>` : '<p class="helper">No thoughts weigh on them.</p>'}
    ${opinions ? `<p class="stage-heading">Opinions</p>${opinions}` : ""}
    ${news ? `<p class="stage-heading">News</p>${news}` : ""}</div></details>`;
}

/** Show the second decision stage: which chair a visitor who decided to sit picked, or which action of a chosen family. */
function seatChoice(actor: Actor): string {
  const family = actor.decision?.family;
  const stage = actor.decision?.seat ?? family;
  if (!stage) return "";
  const heading = family ? `Which ${escape(family.name.replace("_", " "))}?` : "Which seat?";
  return `<p class="stage-heading">${heading} <span class="source-tag">${stage.source === "jev" ? "JEV" : "LOCAL"}</span></p>${scoreList(stage.scores)}${stage.error ? `<p class="decision-error">Fallback: ${escape(stage.error)}</p>` : ""}`;
}

function scoreList(scores: unknown): string {
  if (!scores || typeof scores !== "object" || Object.keys(scores).length === 0) return '<p class="helper">No decision yet.</p>';
  const rows: [string, unknown][] = Array.isArray(scores) ? scores.map((score: unknown, index: number): [string, unknown] => [String(index + 1), score]) : Object.entries(scores);
  return `<div class="score-list">${rows.map(([id, score]: [string, unknown]): string => `<div><span>${escape(id.replaceAll("_", " "))}</span><strong>${typeof score === "number" ? score.toFixed(2) : escape(JSON.stringify(score))}</strong></div>`).join("")}</div>`;
}

function knowledge(actor: Actor): string {
  const objects: [string, Record<string, unknown>][] = Object.entries(actor.knowledge.objects);
  if (!objects.length) return '<p class="helper">Still discovering the room.</p>';
  return objects.map(([id, known]: [string, Record<string, unknown>]): string => `<div class="known-object"><span>${escape(known.name ?? id)}</span><span>${known.kind === "tap" && known.stock !== null && known.stock !== undefined ? `${escape(known.stock)} beers observed` : `${escape(known.kind ?? "known")}${known.reserved_by ? " · reserved" : ""}`}</span></div>`).join("");
}

function memories(actor: Actor): string {
  if (!actor.memory.length) return '<p class="helper">No personal memories yet.</p>';
  return actor.memory.slice(-6).reverse().map((memory: unknown): string => {
    if (typeof memory === "string") return `<p>${escape(memory)}</p>`;
    const record: Record<string, unknown> = memory as Record<string, unknown>;
    return `<p>${escape(record?.message ?? record?.outcome ?? JSON.stringify(memory))}</p>`;
  }).join("");
}
