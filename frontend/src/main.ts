import Phaser from "phaser";
import { WorldConnection } from "./connection";
import { Dashboard } from "./dashboard";
import { LineupScreen } from "./lineupscreen";
import { TavernScene } from "./scene";
import { spriteSheets } from "./sprites";
import { OrderMenu } from "./ordermenu";
import { clickOrder, menuRows, walkAction, type Pick } from "./orders";
import { WheelBar } from "./wheelbar";
import type { Cast, CharacterCatalog, OptionsMessage, Snapshot, World } from "./types";
import "./style.css";

const root: HTMLElement | null = document.querySelector("#app");
if (!root) throw new Error("The app container is missing.");
const application: HTMLElement = root;

/** Return this device's private session ID, kept across visits when storage allows. */
function deviceSession(): string {
  const key: string = "tavern.session";
  try {
    const saved: string | null = localStorage.getItem(key);
    if (saved) return saved;
    const created: string = crypto.randomUUID();
    localStorage.setItem(key, created);
    return created;
  } catch {
    // Without storage (private mode, blocked site data) the evening lasts only for this page.
    return crypto.randomUUID();
  }
}

async function start(): Promise<void> {
  const response: Response = await fetch("/api/characters");
  if (!response.ok) throw new Error(`Could not load the character catalog (${response.status}).`);
  const sprites = spriteSheets(await response.json() as CharacterCatalog);
  const casts: Response = await fetch("/api/casts");
  if (!casts.ok) throw new Error(`Could not load the casts (${casts.status}).`);
  const offered: Cast[] = await casts.json() as Cast[];
  let world: World | null = null;
  let selectedId: string | null = null;
  let connection: WorldConnection;

function selectVisitor(id: string): void {
  selectedId = id;
  scene.select(id);
  dashboard.select(id);
}

/** The target a menu was asked for, and where the click was; the `options` reply opens the menu there. */
let asked: { target_id: string; page: { x: number; y: number } } | null = null;

function steeringNow(): boolean {
  return world?.player?.steering === true;
}

function clicked(pick: Pick, page: { x: number; y: number }): void {
  const order = clickOrder(pick, steeringNow());
  if (order?.kind === "walk") connection.send({ type: "act", action: walkAction(order.cell) });
  if (order?.kind === "ask") { asked = { target_id: order.target_id, page }; connection.send({ type: "options", target_id: order.target_id }); }
  if (order?.kind === "inspect" && pick.kind === "visitor") selectVisitor(order.id);
}

function showMenu(reply: OptionsMessage): void {
  if (!world || !asked || asked.target_id !== reply.target_id) return;
  const names: Record<string, string> = {};
  for (const actor of world.actors) names[actor.id] = actor.name;
  for (const object of world.map.objects) names[object.id] = object.name;
  const target: string = asked.target_id;
  menu.open(menuRows(reply, names), asked.page);
  inspectTarget = (): void => { if (names[target] && world?.actors.some((actor): boolean => actor.id === target)) selectVisitor(target); };
}
let inspectTarget: () => void = (): void => {};

function showError(message: string): void {
  const played: string | undefined = world?.player?.actor_id;
  if (steeringNow() && played) scene.toast(played, message);
  else dashboard.showError(message);
}

const scene: TavernScene = new TavernScene(
  { select: selectVisitor, cell: (): void => {}, hover: (message: string): void => dashboard.hover(message), pick: clicked },
  sprites,
);
const dashboard: Dashboard = new Dashboard(application, {
  command: (command): void => connection.send(command),
  select: selectVisitor,
  lineup: (): void => lineup.open(true),
}, sprites);
const wheelHost: HTMLElement = document.createElement("div");
application.querySelector(".game-surround")?.before(wheelHost);
const wheel: WheelBar = new WheelBar(wheelHost, (command): void => connection.send(command));
const menu: OrderMenu = new OrderMenu(document.body, {
  act: (action): void => connection.send({ type: "act", action }),
  inspect: (): void => inspectTarget(),
});
const lineupHost: HTMLElement = document.createElement("div");
application.append(lineupHost);
const lineup: LineupScreen = new LineupScreen(lineupHost, offered, (command): void => connection.send(command));

const game: Phaser.Game = new Phaser.Game({
  type: Phaser.AUTO,
  parent: "game",
  width: 640,
  height: 448,
  backgroundColor: "#332d29",
  render: { antialias: true, roundPixels: false },
  scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  scene,
});

function applySnapshot(snapshot: Snapshot): void {
  const first: boolean = world === null;
  world = snapshot.state;
  // The screen greets a page that has just opened; an evening restored from a save can be resumed from it.
  if (first) lineup.open(world.tick > 0);
  scene.setWorld(world, snapshot.activities, snapshot.minds);
  dashboard.apply(snapshot);
  wheel.apply(world);
  // Departed visitors stay selectable, so their evening can still be inspected.
  if (!selectedId || ![...world.actors, ...world.departed].some((actor): boolean => actor.id === selectedId)) {
    selectedId = world.actors[0]?.id ?? null;
    scene.select(selectedId);
    dashboard.select(selectedId);
  }
}

connection = new WorldConnection(deviceSession(), {
  snapshot: applySnapshot,
  status: (connected: boolean, message: string): void => dashboard.setConnection(connected, message),
  error: showError,
  options: showMenu,
});

window.addEventListener("pagehide", (): void => { connection.dispose(); game.destroy(true); });
}

void start().catch((error: unknown): void => {
  application.textContent = `Could not open the tavern: ${String(error)}`;
});
