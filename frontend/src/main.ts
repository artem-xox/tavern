import Phaser from "phaser";
import { WorldConnection } from "./connection";
import { Dashboard } from "./dashboard";
import { TavernScene } from "./scene";
import type { Cell, Snapshot, World } from "./types";
import "./style.css";

const root: HTMLElement | null = document.querySelector("#app");
if (!root) throw new Error("The app container is missing.");

let world: World | null = null;
let selectedId: string | null = null;
let editing: boolean = false;
let connection: WorldConnection;

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

function selectVisitor(id: string): void {
  selectedId = id;
  scene.select(id);
  dashboard.select(id);
}

function editCell(x: number, y: number): void {
  if (!world || !editing) return;
  const blocked: boolean = world.map.blocked.some(([cellX, cellY]: Cell): boolean => cellX === x && cellY === y);
  connection.send({ type: "block", x, y, blocked: !blocked });
}

const scene: TavernScene = new TavernScene(
  { select: selectVisitor, cell: editCell, hover: (message: string): void => dashboard.hover(message) },
);
const dashboard: Dashboard = new Dashboard(root, {
  command: (command): void => connection.send(command),
  select: selectVisitor,
  edit: (enabled: boolean): void => { editing = enabled; scene.setEditing(enabled); },
});

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
  world = snapshot.state;
  scene.setWorld(world, snapshot.activities);
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
