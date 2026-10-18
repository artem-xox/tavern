import Phaser from "phaser";
import { WorldConnection } from "./connection";
import { Dashboard } from "./dashboard";
import { LineupScreen } from "./lineupscreen";
import { TavernScene } from "./scene";
import { spriteSheets } from "./sprites";
import type { Cast, CharacterCatalog, Snapshot, World } from "./types";
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

const scene: TavernScene = new TavernScene(
  { select: selectVisitor, cell: (): void => {}, hover: (message: string): void => dashboard.hover(message) },
  sprites,
);
const dashboard: Dashboard = new Dashboard(application, {
  command: (command): void => connection.send(command),
  select: selectVisitor,
  lineup: (): void => lineup.open(true),
}, sprites);
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
  error: (message: string): void => dashboard.showError(message),
});

window.addEventListener("pagehide", (): void => { connection.dispose(); game.destroy(true); });
}

void start().catch((error: unknown): void => {
  application.textContent = `Could not open the tavern: ${String(error)}`;
});
