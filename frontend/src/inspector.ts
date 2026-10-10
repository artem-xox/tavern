/** The inspector panel: one visitor's story first, then what lies behind it, drawn into its container. */
import { html, render, svg, type TemplateResult } from "lit-html";
import { aimLabel } from "./aims";
import { clock } from "./clock";
import { iconPixels } from "./icons";
import { projectLabel } from "./projects";
import { mergeThoughts, NEED_PIPS, needPips, needTone, needWord, opinionBar, type MergedThought } from "./mindview";
import { spriteOf } from "./sprites";
import type { ActivityView, Actor, ItemView, Mind, NewsCopy, Verb, World, WorldObject } from "./types";

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

/** The needs in the order they are shown, with the word for each; the server's `fatigue` is energy and `boredom` is fun. */
const NEEDS: readonly (readonly [keyof Actor["needs"], string])[] = [
  ["thirst", "Thirst"], ["bladder", "Bladder"], ["fatigue", "Energy"], ["social", "Company"], ["boredom", "Fun"],
];

const signed = (value: number): string => `${value > 0 ? "+" : value < 0 ? "−" : ""}${Math.abs(Math.round(value))}`;
const sentence = (text: string): string => text.charAt(0).toUpperCase() + text.slice(1);

/**
 * Draw the inspector for `actor` into `inspector`.
 *
 * lit-html keeps every element the template already made and changes only what differs, so a snapshot every
 * 100 ms never replaces a section or a button under the pointer, and a `<details>` the user opened stays
 * open for every visitor. The sections behind the story start closed.
 */
export function renderInspector(inspector: HTMLElement, actor: Actor, ctx: InspectorContext): void {
  const mind: Mind | undefined = ctx.minds[actor.id];
  render(html`${header(actor, ctx, mind)}${now(actor, ctx)}
    <div class="insp-section"><p class="eyebrow"><span>Needs</span><span>full is fine</span></p>${needs(actor)}</div>
    <div class="insp-section"><p class="eyebrow"><span>Carrying</span><span></span></p>${slots(actor, ctx)}${visit(actor, ctx)}</div>
    ${mind ? feelings(mind) : ""}${mind ? people(mind) : ""}${mind ? news(mind) : ""}
    <details id="traits-detail"><summary><span>Character</span><span>${Object.keys(actor.traits).length} traits</span></summary><div class="detail-body"><div class="traits">${Object.entries(actor.traits).map(([key, value]: [string, unknown]) => html`<span>${key.replaceAll("_", " ")} ${value}</span>`)}</div></div></details>
    <details id="decision-detail"><summary><span>Why this decision?</span><span>${actor.decision?.source === "jev" ? "JEV" : "LOCAL"}</span></summary><div class="detail-body">${scoreList(actor.decision?.scores)}${actor.decision?.error ? html`<p class="decision-error">Fallback: ${actor.decision.error}</p>` : ""}${seatChoice(actor)}${aimChoice(actor)}</div></details>
    <details id="knowledge-detail"><summary><span>What they know</span><span>${Object.keys(actor.knowledge.objects).length}</span></summary><div class="detail-body">${knowledge(actor)}</div></details>
    <details id="memory-detail"><summary><span>Recent memories</span><span>${actor.memory.length}</span></summary><div class="detail-body memories">${memories(actor)}</div></details>`, inspector);
}

/**
 * Draw what only the one debugging needs into the Debug section's container: raw numbers, timers and chains.
 *
 * @param readout The container inside the Debug `<details>`.
 */
export function renderDebug(readout: HTMLElement, actor: Actor, ctx: InspectorContext): void {
  const mind: Mind | undefined = ctx.minds[actor.id];
  const written = actor.intention;
  render(html`
    <div class="row"><span>Needs as urgency</span><span>${NEEDS.map(([key, label]: readonly [keyof Actor["needs"], string]) => `${label.toLowerCase()} ${Math.round(actor.needs[key])}`).join(" · ")}</span></div>
    <div class="row"><span>Drunkenness</span><span>${mind ? `${Math.round(mind.drunkenness * 100)}%` : "unknown"}</span></div>
    <div class="row"><span>Path</span><span>${actor.path.length ? `${actor.path.length} steps remaining` : "none"}</span></div>
    ${written ? html`<div class="row"><span>Intention</span><span>${Math.max(0, Math.round(ctx.world.time - written.written_at))} s ago, after: ${written.trigger.text}</span></div>` : html`<div class="row"><span>Intention</span><span>${ctx.intentions ? "none written yet" : "offline: no Claude key"}</span></div>`}
    ${(mind?.thoughts ?? []).map((thought) => html`<div class="row"><span>Thought: ${thought.text}</span><span>${Math.max(0, Math.ceil(thought.expires_at - ctx.world.time))}\u00a0s left</span></div>`)}
    ${(mind?.news ?? []).map((copy: NewsCopy) => html`<div class="row"><span>News: ${copy.topic}${copy.overheard ? " · overheard" : ""} · ${copy.chain.join(" ← ")}</span><span>${Math.round(copy.confidence * 100)}%</span></div>`)}`, readout);
}

/** The portrait, the name, what the guest is doing, and two chips: their mood and their drink. */
function header(actor: Actor, ctx: InspectorContext, mind: Mind | undefined): TemplateResult {
  const tone: string = !mind ? "" : mind.mood >= 3 ? "good" : mind.mood <= -3 ? "bad" : "";
  return html`<div class="who" style="--visitor:${ctx.color}">
    <div class="portrait"><img alt="" src="/characters/${spriteOf(actor).name}/Idle/rotations/south.png"></div>
    <div><h2>${actor.name}</h2><p class="doing">${sentence(ctx.status)}</p>
      ${mind ? html`<div class="chips"><span class="chip ${tone}" title="mood ${signed(mind.mood)}">${sentence(mind.mood_words)}</span><span class="chip" title="drunkenness ${Math.round(mind.drunkenness * 100)}%">${sentence(mind.stage)}</span>${actor.ailing ? html`<span class="chip bad" title="came in with a fever; a herbal remedy would cure them">Unwell</span>` : ""}${actor.health < 70 || actor.condition !== "ok" ? html`<span class="chip bad" title="health ${Math.round(actor.health)} of 100; a remedy or a bed would mend them">${actor.condition === "out" ? "Knocked out" : actor.condition === "down" ? "Thrown down" : actor.condition === "groggy" ? "Groggy" : "Hurt"} ${Math.round(actor.health)}</span>` : ""}</div>` : ""}</div></div>`;
}

/** What the guest is doing and where, the thought behind it in their own words, and what they intend. */
function now(actor: Actor, ctx: InspectorContext): TemplateResult {
  const target: WorldObject | undefined = ctx.world.map.objects.find((object: WorldObject): boolean => object.id === actor.action?.target_id);
  const partner: Actor | undefined = ctx.world.actors.find((visitor: Actor): boolean => visitor.id === actor.action?.target_id);
  const action: string = ctx.departed ? "Gone home" : actor.action ? ctx.activities[actor.action.verb]?.label ?? actor.action.verb : actor.seat_id ? "Settled at the table" : "Considering the next move";
  const place: string = actor.visit.left_at !== undefined ? `Left at ${clock(actor.visit.left_at)}` : target ? target.name : partner ? `With ${partner.name}` : "";
  const written = actor.intention;
  const goal: string = written?.goal ? `${written.goal.kind.replace("_", " ")} ${ctx.world.actors.find((item: Actor): boolean => item.id === written.goal?.target)?.name ?? written.goal.target}` : "";
  const plan = ctx.world.projects.find((item) => item.by === actor.id);
  return html`<div class="now"><p class="action">${action}</p><p class="where">${place}</p>${plan ? html`<p class="where">${projectLabel(plan.kind, plan.step, plan.of)}</p>` : ""}
    ${written ? html`<p class="thought">“${written.thought}”</p><p class="intends"><b>Intends</b> ${written.intention}</p>${goal ? html`<span class="goal" title="${written.goal?.status ?? ""}">Goal · ${goal}</span>` : ""}`
      : html`<p class="quiet">${ctx.intentions ? "No intention written yet." : "Offline: no Claude key, so guests write no intentions."}</p>`}</div>`;
}

/** Each need as five pips of satisfaction: a full row is a content guest; the exact urgency is the tooltip. */
function needs(actor: Actor): TemplateResult {
  return html`<div class="needs">${NEEDS.map(([key, label]: readonly [keyof Actor["needs"], string]) => {
    const pips: number = needPips(actor.needs[key]);
    return html`<div class="need ${needTone(pips)}" title="${key}: urgency ${Math.round(actor.needs[key])}/100"><span class="label">${label}</span>
      <span class="pips">${Array.from({ length: NEED_PIPS }, (_: unknown, index: number) => html`<i class="pip ${index < pips ? "on" : ""}"></i>`)}</span><span class="word">${needWord(pips)}</span></div>`;
  })}</div>`;
}

/**
 * What the guest carries as an inventory: one slot per item kind the server knows, in its order. A carried kind
 * shows its picture and, above one, a count; the others are dim and empty. The tooltip is the server's wording.
 */
function slots(actor: Actor, ctx: InspectorContext): TemplateResult {
  return html`<div class="slots" role="list">${Object.entries(ctx.items).map(([kind, words]: [string, ItemView]) => {
    const count: number = actor.inventory[kind] ?? 0;
    if (count === 0) return html`<div class="slot empty" role="listitem" title="no ${words.many}" aria-label="no ${words.many}"></div>`;
    const label: string = count === 1 ? words.one : `${count} ${words.many}`;
    return html`<div class="slot" role="listitem" title="${label}" aria-label="${label}">${icon(kind)}${count > 1 ? html`<span class="count">${count}</span>` : ""}</div>`;
  })}</div>`;
}

/** An item's picture as an SVG of one square per pixel, kept crisp at any size. */
function icon(kind: string): TemplateResult {
  const { size, pixels } = iconPixels(kind);
  return html`<svg viewBox="0 0 ${size} ${size}" width="32" height="32" shape-rendering="crispEdges" aria-hidden="true">${pixels.map((pixel) => svg`<rect x="${pixel.x}" y="${pixel.y}" width="1" height="1" fill="${pixel.color}"/>`)}</svg>`;
}

/** Summarize tonight's visit: time here, beers and own seat. */
function visit(actor: Actor, ctx: InspectorContext): TemplateResult {
  const seat: WorldObject | undefined = ctx.world.map.objects.find((object: WorldObject): boolean => object.id === actor.favorite_seat_id);
  return html`<div class="meta"><span>Here <b>${clock(actor.visit.seconds)}</b></span><span>${actor.visit.beers === 1 ? "Ale" : "Ales"} <b>${actor.visit.beers}</b></span><span>Own seat <b>${seat ? seat.name : "not chosen yet"}</b></span></div>`;
}

/** The thoughts weighing on the mood, those with the same words merged, with their effect. */
function feelings(mind: Mind): TemplateResult {
  const rows: MergedThought[] = mergeThoughts(mind.thoughts);
  return html`<div class="insp-section"><p class="eyebrow"><span>Feelings</span><span>mood ${signed(mind.mood)}</span></p>
    ${rows.length ? html`<ul class="feel">${rows.map((row: MergedThought) => html`<li class="${row.mood < 0 ? "bad" : "good"}"><span>${row.text}${row.count > 1 ? html`<small>×${row.count}</small>` : ""}</span><strong>${signed(row.mood)}</strong></li>`)}</ul>` : html`<p class="quiet">Nothing weighs on them.</p>`}</div>`;
}

/** What they think of each person they know: a bar from the middle, and how well they know them. */
function people(mind: Mind): TemplateResult | string {
  if (!mind.opinions.length) return "";
  return html`<div class="insp-section"><p class="eyebrow"><span>People</span><span></span></p>${mind.opinions.map((opinion) => {
    const bar = opinionBar(opinion.opinion);
    return html`<div class="person"><span>${opinion.name}<span class="rel">${opinion.familiarity}</span></span><div class="opinion" title="opinion ${signed(opinion.opinion)}"><i class="${bar.side}" style="width:${bar.percent}%"></i></div></div>`;
  })}</div>`;
}

/** The news they carry, as they would tell it. */
function news(mind: Mind): TemplateResult | string {
  if (!mind.news.length) return "";
  return html`<div class="insp-section"><p class="eyebrow"><span>News</span><span></span></p>${mind.news.map((copy: NewsCopy) => html`<p class="news-topic">${copy.topic}</p><p class="news-quote">“${copy.told_as}”</p>`)}</div>`;
}

/** Show the second decision stage: which chair a visitor who decided to sit picked, or which action of a chosen family. */
function seatChoice(actor: Actor): TemplateResult | string {
  const family = actor.decision?.family;
  const stage = actor.decision?.seat ?? family;
  if (!stage) return "";
  const heading: string = family ? `Which ${family.name.replace("_", " ")}?` : "Which seat?";
  return html`<p class="stage-heading">${heading} <span class="source-tag">${stage.source === "jev" ? "JEV" : "LOCAL"}</span></p>${scoreList(stage.scores)}${stage.error ? html`<p class="decision-error">Fallback: ${stage.error}</p>` : ""}`;
}

/** Show the third decision stage: what a visitor who chose to talk came for. */
function aimChoice(actor: Actor): TemplateResult | string {
  const stage = actor.decision?.aim;
  if (!stage) return "";
  return html`<p class="stage-heading">Came for: ${aimLabel(stage.name)} <span class="source-tag">${stage.source === "jev" ? "JEV" : "LOCAL"}</span></p>${scoreList(stage.scores)}${stage.error ? html`<p class="decision-error">Fallback: ${stage.error}</p>` : ""}`;
}

function scoreList(scores: unknown): TemplateResult {
  if (!scores || typeof scores !== "object" || Object.keys(scores).length === 0) return html`<p class="quiet">No decision yet.</p>`;
  const rows: [string, unknown][] = Array.isArray(scores) ? scores.map((score: unknown, index: number): [string, unknown] => [String(index + 1), score]) : Object.entries(scores);
  return html`<div class="score-list">${rows.map(([id, score]: [string, unknown]) => html`<div class="row"><span>${id.replaceAll("_", " ")}</span><span>${typeof score === "number" ? score.toFixed(2) : JSON.stringify(score)}</span></div>`)}</div>`;
}

function knowledge(actor: Actor): TemplateResult | TemplateResult[] {
  const objects: [string, Record<string, unknown>][] = Object.entries(actor.knowledge.objects);
  if (!objects.length) return html`<p class="quiet">Still discovering the room.</p>`;
  return objects.map(([id, known]: [string, Record<string, unknown>]) => html`<div class="row"><span>${known.name ?? id}</span><span>${known.kind === "tap" && known.stock !== null && known.stock !== undefined ? `${known.stock} beers observed` : `${known.kind ?? "known"}${known.reserved_by ? " · reserved" : ""}`}</span></div>`);
}

function memories(actor: Actor): TemplateResult | TemplateResult[] {
  if (!actor.memory.length) return html`<p class="quiet">No personal memories yet.</p>`;
  return actor.memory.slice(-6).reverse().map((memory: unknown): TemplateResult => {
    if (typeof memory === "string") return html`<p>${memory}</p>`;
    const record: Record<string, unknown> = memory as Record<string, unknown>;
    return html`<p>${record?.message ?? record?.outcome ?? JSON.stringify(memory)}</p>`;
  });
}
