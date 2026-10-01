import Phaser from "phaser";
import type { Actor, Cell, World, WorldObject } from "./types";

interface SceneCallbacks {
  select: (actorId: string) => void;
  cell: (x: number, y: number) => void;
  hover: (message: string) => void;
}

interface ActorView {
  container: Phaser.GameObjects.Container;
  name: Phaser.GameObjects.Text;
  status: Phaser.GameObjects.Text;
  selection: Phaser.GameObjects.Arc;
  mug: Phaser.GameObjects.Container;
  speech: Phaser.GameObjects.Text;
  targetX: number;
  targetY: number;
}

/** Render server snapshots; interpolation changes display coordinates only. */
export class TavernScene extends Phaser.Scene {
  private world: World | null = null;
  private floor!: Phaser.GameObjects.Graphics;
  private furniture!: Phaser.GameObjects.Graphics;
  private route!: Phaser.GameObjects.Graphics;
  private labels!: Phaser.GameObjects.Group;
  private readonly visitors: Map<string, ActorView> = new Map();
  private mapSignature: string = "";
  private selectedId: string | null = null;
  private editing: boolean = false;
  private ready: boolean = false;

  constructor(private readonly callbacks: SceneCallbacks) {
    super("tavern");
  }

  /** Create rendering layers and map pointer events to server cell coordinates. */
  create(): void {
    this.floor = this.add.graphics();
    this.furniture = this.add.graphics();
    this.labels = this.add.group();
    this.route = this.add.graphics();
    this.input.on("pointerdown", (pointer: Phaser.Input.Pointer): void => this.click(pointer));
    this.input.on("pointermove", (pointer: Phaser.Input.Pointer): void => this.hover(pointer));
    this.ready = true;
    if (this.world) this.setWorld(this.world);
  }

  /** Apply a world snapshot, keeping authoritative actors separate from sprites. */
  setWorld(world: World): void {
    const reset: boolean = this.world !== null && world.tick < this.world.tick;
    this.world = world;
    if (!this.ready) return;
    this.renderMap(world);
    this.syncVisitors(world, reset);
    this.drawRoute();
  }

  /** Select a visitor and show their server-provided route. */
  select(actorId: string | null): void {
    this.selectedId = actorId;
    for (const [id, view] of this.visitors) view.selection.setVisible(id === actorId);
    if (this.ready) this.drawRoute();
  }

  /** Change pointer behavior between visitor inspection and obstacle editing. */
  setEditing(editing: boolean): void {
    this.editing = editing;
    this.input.setDefaultCursor(editing ? "crosshair" : "pointer");
    if (this.ready) this.drawRoute();
  }

  /** Smooth visual movement between discrete authoritative positions. */
  update(_time: number, delta: number): void {
    const blend: number = 1 - Math.exp(-delta / 90);
    for (const view of this.visitors.values()) {
      view.container.x += (view.targetX - view.container.x) * blend;
      view.container.y += (view.targetY - view.container.y) * blend;
    }
  }

  private renderMap(world: World): void {
    const signature: string = JSON.stringify(world.map);
    if (signature === this.mapSignature) return;
    this.mapSignature = signature;
    this.scale.resize(world.map.width * world.map.tile_size, world.map.height * world.map.tile_size);
    this.labels.clear(true, true);
    this.drawFloor(world);
    this.furniture.clear();
    for (const object of world.map.objects) this.drawObject(object, world.map.tile_size);
  }

  private drawFloor(world: World): void {
    const { width, height, tile_size: size, blocked } = world.map;
    this.floor.clear();
    for (let y: number = 0; y < height; y += 1) {
      for (let x: number = 0; x < width; x += 1) {
        this.floor.fillStyle([0x896649, 0x936e4d, 0x8d694a][(x + y * 3) % 3]!);
        this.floor.fillRect(x * size, y * size, size, size);
        this.floor.lineStyle(1, 0x382f26, 0.23);
        this.floor.lineBetween(x * size, (y + 1) * size, (x + 1) * size, (y + 1) * size);
        this.floor.lineBetween((x + (y % 2 ? 0.5 : 0)) * size, y * size, (x + (y % 2 ? 0.5 : 0)) * size, (y + 1) * size);
        this.floor.lineStyle(1, 0xe2b887, 0.09);
        this.floor.lineBetween(x * size + 3, y * size + 10, (x + 1) * size - 3, y * size + 10);
      }
    }
    this.drawRoomDetails(size);
    for (const [x, y] of blocked) this.drawWall(x * size, y * size, size);
    this.drawWindows(size);
  }

  private drawRoomDetails(size: number): void {
    this.floor.fillStyle(0x57372e, 0.4).fillRoundedRect(5.2 * size, 4.6 * size, 5.7 * size, 5.0 * size, 7);
    this.floor.fillStyle(0x8d463a).fillRoundedRect(5.3 * size, 4.7 * size, 5.5 * size, 4.8 * size, 5);
    this.floor.lineStyle(2, 0xd2a367, 0.6).strokeRoundedRect(5.5 * size, 4.9 * size, 5.1 * size, 4.4 * size, 3);
    for (let row: number = 0; row < 4; row += 1) {
      for (let col: number = 0; col < 5; col += 1) {
        const x: number = (5.9 + col) * size;
        const y: number = (5.4 + row) * size;
        this.floor.lineStyle(1, 0xdfb476, 0.15).strokePoints([{ x, y: y - 6 }, { x: x + 6, y }, { x, y: y + 6 }, { x: x - 6, y }], true);
      }
    }
    this.floor.fillStyle(0x526455, 0.6).fillRoundedRect(11.5 * size, 8.4 * size, 4.8 * size, 2.3 * size, 5);
    this.floor.lineStyle(1, 0xabbd92, 0.5).strokeRoundedRect(11.7 * size, 8.6 * size, 4.4 * size, 1.9 * size, 3);
    this.floor.fillStyle(0xb9afa0).fillRect(16 * size, size, 3 * size, 3 * size);
    for (let x: number = 16; x < 19; x += 1) {
      for (let y: number = 1; y < 4; y += 1) {
        this.floor.lineStyle(1, 0x777e72, 0.4).strokeRect(x * size, y * size, size, size);
        this.floor.fillStyle(0x667568, 0.25).fillRect((x + 0.45) * size, (y + 0.45) * size, 4, 4);
      }
    }
    this.floor.fillStyle(0x41372a).fillRoundedRect(8.5 * size, 11.8 * size, 3 * size, size * 0.7, 3);
    this.floor.lineStyle(1, 0xb29762, 0.6).strokeRoundedRect(8.65 * size, 11.9 * size, 2.7 * size, size * 0.5, 2);
    this.floor.fillStyle(0xddd1aa, 0.35).fillRect(3.3 * size, 9.2 * size, 3, size * 0.6);
    for (const [x, y] of [[2, 2], [12, 2], [18, 7]]) {
      for (let radius: number = 3; radius > 0; radius -= 1) {
        this.floor.fillStyle(0xf5ce82, 0.025).fillCircle((x! + 0.5) * size, (y! + 0.5) * size, radius * size);
      }
    }
  }

  private drawWindows(size: number): void {
    for (const y of [3, 7, 10]) {
      this.floor.fillStyle(0x403e34).fillRoundedRect(5, y * size + 3, 22, 26, 2);
      this.floor.fillStyle(0x88a39c).fillRect(9, y * size + 6, 14, 19);
      this.floor.lineStyle(2, 0xd3b584).lineBetween(16, y * size + 6, 16, y * size + 25);
      this.floor.lineBetween(9, y * size + 15, 23, y * size + 15);
      this.floor.fillStyle(0xc7a272).fillRect(6, y * size + 26, 23, 4);
    }
    this.floor.fillStyle(0x634835).fillRoundedRect(8.5 * size, 13 * size + 1, 3 * size, 26, 3);
    for (let x: number = 9; x <= 11; x += 1) {
      this.floor.lineStyle(1, 0xc0a16d, 0.5).lineBetween(x * size, 13 * size + 5, x * size, 13 * size + 25);
    }
  }

  private drawWall(x: number, y: number, size: number): void {
    this.floor.fillStyle(0x332d29);
    this.floor.fillRect(x, y, size, size);
    this.floor.fillStyle(0x555048);
    this.floor.fillRoundedRect(x + 2, y + 2, size - 4, size - 5, 3);
    this.floor.lineStyle(2, 0x756b5b, 0.55);
    this.floor.lineBetween(x + 4, y + 3, x + size - 5, y + 3);
    this.floor.lineStyle(1, 0x292724, 0.5);
    this.floor.lineBetween(x + size / 2, y + 4, x + size / 2, y + size - 4);
  }

  private drawObject(object: WorldObject, size: number): void {
    const x: number = (object.x + 0.5) * size;
    const y: number = (object.y + 0.5) * size;
    this.furniture.fillStyle(0x1e1914, 0.32);
    this.furniture.fillEllipse(x + ((object.width ?? 1) - 1) * size / 2, y + 10, size * (object.width ?? 1) * 0.9, 12);
    if (object.kind === "tap") this.drawTap(x, y);
    if (object.kind === "toilet") this.drawToilet(x, y);
    if (object.kind === "chair") this.drawChair(x, y, object.facing);
    if (object.kind === "bar") this.drawBar(object, size);
    if (object.kind === "table") this.drawTable(object, size);
    if (object.kind === "darts") this.drawDarts(x, y);
    if (object.reserved_by) this.furniture.lineStyle(2, 0xe6c88d, 0.75).strokeCircle(x, y, 15);
    if (["tap", "toilet", "darts"].includes(object.kind)) this.objectLabel(object, x, y);
  }

  private drawTap(x: number, y: number): void {
    this.furniture.fillStyle(0x3f3528).fillRoundedRect(x - 13, y - 14, 26, 29, 5);
    this.furniture.fillStyle(0xb8803c).fillRoundedRect(x - 10, y - 12, 20, 24, 4);
    this.furniture.lineStyle(3, 0x674b32).lineBetween(x - 9, y - 7, x + 9, y - 7);
    this.furniture.lineBetween(x - 9, y + 7, x + 9, y + 7);
    this.furniture.fillStyle(0xe8c873).fillRect(x - 3, y - 3, 6, 14);
    this.furniture.fillRect(x - 2, y + 5, 9, 4);
  }

  private drawToilet(x: number, y: number): void {
    this.furniture.fillStyle(0xa1aea0).fillRoundedRect(x - 10, y - 13, 20, 9, 3);
    this.furniture.fillStyle(0xe3e6cd).fillEllipse(x, y + 3, 21, 25);
    this.furniture.fillStyle(0x52685d).fillEllipse(x, y + 1, 12, 15);
    this.furniture.lineStyle(2, 0xf2eed9).strokeEllipse(x, y + 1, 15, 18);
  }

  private drawChair(x: number, y: number, facing: WorldObject["facing"]): void {
    this.furniture.fillStyle(0x4d3425).fillRoundedRect(x - 11, y - 12, 22, 25, 3);
    this.furniture.fillStyle(0xa2774d).fillRoundedRect(x - 8, y - 3, 16, 13, 2);
    this.furniture.fillStyle(0xc09867);
    if (facing === "east") this.furniture.fillRoundedRect(x - 12, y - 10, 7, 20, 2);
    else if (facing === "west") this.furniture.fillRoundedRect(x + 5, y - 10, 7, 20, 2);
    else if (facing === "north") this.furniture.fillRoundedRect(x - 10, y + 5, 20, 7, 2);
    else this.furniture.fillRoundedRect(x - 10, y - 12, 20, 7, 2);
    this.furniture.fillStyle(0x905b3d).fillRoundedRect(x - 5, y - 4, 10, 11, 2);
  }

  private drawBar(object: WorldObject, size: number): void {
    const x: number = object.x * size;
    const y: number = object.y * size;
    const width: number = (object.width ?? 1) * size;
    this.furniture.fillStyle(0x3e2b20).fillRoundedRect(x - 2, y + 4, width + 4, size, 4);
    this.furniture.fillStyle(0xb78650).fillRoundedRect(x - 3, y - 2, width + 6, size - 5, 4);
    this.furniture.fillStyle(0x6f4930).fillRoundedRect(x + 2, y + 2, width - 4, size - 13, 2);
    this.furniture.lineStyle(2, 0xe3bd7f).lineBetween(x + 2, y + 2, x + width - 2, y + 2);
    this.furniture.lineStyle(3, 0xcfab67).lineBetween(x + 5, y + size + 3, x + width - 5, y + size + 3);
    for (let i: number = 0; i < 3; i += 1) {
      this.furniture.fillStyle([0x678167, 0xb87946, 0x71868a][i]!).fillRoundedRect(x + 12 + i * 12, y + 7, 6, 10, 2);
      this.furniture.fillRect(x + 14 + i * 12, y + 3, 2, 6);
    }
    this.drawMug(x + width - 19, y + 10);
  }

  private drawTable(object: WorldObject, size: number): void {
    const x: number = object.x * size;
    const y: number = object.y * size;
    const width: number = (object.width ?? 1) * size;
    const height: number = (object.height ?? 1) * size;
    this.furniture.fillStyle(0x33251d, 0.5).fillRoundedRect(x - 2, y + 5, width + 4, height, 8);
    this.furniture.fillStyle(0x58392a).fillRoundedRect(x - 2, y - 2, width + 4, height + 4, 6);
    this.furniture.fillStyle(0xb48959).fillRoundedRect(x + 1, y + 1, width - 2, height - 2, 5);
    for (let row: number = 12; row < height; row += 14) {
      this.furniture.lineStyle(1, 0x785037, 0.5).lineBetween(x + 4, y + row, x + width - 4, y + row);
    }
    this.furniture.lineStyle(1, 0xe6c187, 0.6).strokeRoundedRect(x + 3, y + 3, width - 6, height - 6, 3);
    this.furniture.fillStyle(0xe8dbc0).fillRoundedRect(x + width - 19, y + height - 19, 11, 10, 1);
    this.drawMug(x + 13, y + 13);
    this.drawMug(x + width - 13, y + height - 12);
    const cx: number = x + width / 2;
    const cy: number = y + height / 2;
    this.furniture.fillStyle(0xf8d281, 0.1).fillCircle(cx, cy, 18);
    this.furniture.fillStyle(0x69553a).fillEllipse(cx, cy + 3, 14, 8);
    this.furniture.fillStyle(0xf2dfae).fillRect(cx - 2, cy - 6, 4, 10);
    this.furniture.fillStyle(0xffd884).fillEllipse(cx, cy - 8, 4, 7);
  }

  private drawMug(x: number, y: number): void {
    this.furniture.lineStyle(2, 0xe6d5ad).strokeRoundedRect(x + 1, y - 2, 7, 7, 2);
    this.furniture.fillStyle(0xcea15e).fillRoundedRect(x - 4, y - 5, 8, 12, 2);
    this.furniture.fillStyle(0xf5e3b6).fillEllipse(x, y - 4, 9, 4);
  }

  private drawDarts(x: number, y: number): void {
    this.furniture.fillStyle(0x3b2b22).fillRoundedRect(x - 15, y - 16, 30, 33, 4);
    this.furniture.fillStyle(0xb69769).fillCircle(x, y, 13);
    this.furniture.fillStyle(0x243a31).fillCircle(x, y, 11);
    this.furniture.lineStyle(2, 0xbb6954).strokeCircle(x, y, 8);
    for (let i: number = 0; i < 12; i += 1) {
      const angle: number = i * Math.PI / 6;
      this.furniture.lineStyle(1, 0xe4d3aa, 0.6).lineBetween(x + Math.cos(angle) * 3, y + Math.sin(angle) * 3, x + Math.cos(angle) * 11, y + Math.sin(angle) * 11);
    }
    this.furniture.fillStyle(0xce7358).fillCircle(x, y, 3);
    this.furniture.lineStyle(2, 0xe5c178).lineBetween(x + 1, y - 3, x + 8, y - 10);
  }

  private objectLabel(object: WorldObject, x: number, y: number): void {
    const title: string = object.kind === "tap" ? `${object.name} · ${object.stock ?? 0}` : object.name;
    const label: Phaser.GameObjects.Text = this.add.text(x, y - 22, title, {
      fontFamily: "system-ui, sans-serif", fontSize: "10px", color: "#f6dfb9",
      backgroundColor: "#352b24", padding: { x: 5, y: 3 },
    }).setOrigin(0.5, 1);
    this.labels.add(label);
  }

  private syncVisitors(world: World, reset: boolean): void {
    const ids: Set<string> = new Set(world.actors.map((actor: Actor): string => actor.id));
    for (const [id, view] of this.visitors) {
      if (!ids.has(id)) { view.container.destroy(); this.visitors.delete(id); }
    }
    for (const actor of world.actors) {
      let view: ActorView | undefined = this.visitors.get(actor.id);
      if (!view) { view = this.createVisitor(actor); this.visitors.set(actor.id, view); }
      this.updateVisitor(view, actor, world.map.tile_size, reset);
    }
  }

  private createVisitor(actor: Actor): ActorView {
    const color: number = Phaser.Display.Color.ValueToColor(actor.color).color;
    const shadow: Phaser.GameObjects.Ellipse = this.add.ellipse(0, 9, 25, 12, 0x191815, 0.4);
    const selection: Phaser.GameObjects.Arc = this.add.circle(0, 0, 16).setStrokeStyle(2, 0xffe0a3).setVisible(actor.id === this.selectedId);
    const body: Phaser.GameObjects.Ellipse = this.add.ellipse(0, 3, 18, 19, color).setStrokeStyle(2, 0x3b362d);
    const face: Phaser.GameObjects.Arc = this.add.circle(0, -6, 7, 0xebbd91);
    const hair: Phaser.GameObjects.Ellipse = this.add.ellipse(0, -11, 14, 7, 0x49342d);
    const name: Phaser.GameObjects.Text = this.add.text(0, -24, actor.name, { fontFamily: "system-ui", fontSize: "11px", color: "#fff4dc", stroke: "#322b24", strokeThickness: 3 }).setOrigin(0.5);
    const status: Phaser.GameObjects.Text = this.add.text(0, 22, actor.status, { fontFamily: "system-ui", fontSize: "9px", color: "#ead6b6", backgroundColor: "#302b25b0", padding: { x: 3, y: 1 } }).setOrigin(0.5);
    const mugBody: Phaser.GameObjects.Rectangle = this.add.rectangle(0, 0, 7, 10, 0xd6a252);
    const foam: Phaser.GameObjects.Ellipse = this.add.ellipse(0, -5, 8, 4, 0xffebc2);
    const mug: Phaser.GameObjects.Container = this.add.container(12, 3, [mugBody, foam]);
    const speech: Phaser.GameObjects.Text = this.add.text(0, -44, "", { fontFamily: "Georgia", fontSize: "10px", color: "#48392b", backgroundColor: "#f4e6c6", padding: { x: 6, y: 4 } }).setOrigin(0.5).setVisible(false);
    const container: Phaser.GameObjects.Container = this.add.container(0, 0, [shadow, selection, body, face, hair, name, status, mug, speech]);
    return { container, name, status, selection, mug, speech, targetX: 0, targetY: 0 };
  }

  private updateVisitor(view: ActorView, actor: Actor, size: number, reset: boolean): void {
    const x: number = (actor.x + 0.5) * size;
    const y: number = (actor.y + 0.5) * size;
    if (reset || view.targetX === 0 || Math.hypot(x - view.container.x, y - view.container.y) > size * 3) view.container.setPosition(x, y);
    view.targetX = x;
    view.targetY = y;
    view.name.setText(actor.name);
    const incoming: Actor | undefined = this.world?.actors.find((visitor: Actor): boolean => visitor.action?.verb === "talk" && visitor.action.target_id === actor.id);
    const chatting: boolean = !!incoming || actor.action?.verb === "talk";
    const labels: Record<string, string> = { sit: "seated", talk: "chatting", play_darts: "darts", take_beer: "getting ale", drink: "sipping ale", use_toilet: "WC" };
    view.status.setText(actor.status === "walking" ? `→ ${labels[actor.action?.verb ?? ""] ?? "exploring"}` : chatting ? "chatting" : actor.action ? labels[actor.action.verb] ?? actor.action.verb : actor.seat_id ? "seated" : "thinking");
    view.mug.setVisible(actor.inventory.beer > 0);
    view.speech.setVisible(chatting);
    view.speech.setText(incoming ? "Quite a story!" : "News from the road…");
    view.container.setDepth(10 + y / 1000);
  }

  private drawRoute(): void {
    this.route.clear();
    if (!this.world) return;
    const size: number = this.world.map.tile_size;
    const actor: Actor | undefined = this.world.actors.find((visitor: Actor): boolean => visitor.id === this.selectedId);
    if (actor && actor.path.length > 0) {
      const cells: Cell[] = [[actor.x, actor.y], ...actor.path];
      this.route.lineStyle(2, 0xf3d297, 0.8).beginPath();
      cells.forEach(([x, y]: Cell, index: number): void => {
        if (index === 0) this.route.moveTo((x + 0.5) * size, (y + 0.5) * size);
        else this.route.lineTo((x + 0.5) * size, (y + 0.5) * size);
      });
      this.route.strokePath();
      for (const [x, y] of actor.path) this.route.fillStyle(0xf3d297, 0.75).fillCircle((x + 0.5) * size, (y + 0.5) * size, 3);
    }
    if (this.editing) {
      for (const object of this.world.map.objects) {
        for (const [x, y] of object.interaction_spots) this.route.lineStyle(1, 0xe9d8a6, 0.4).strokeRect(x * size + 7, y * size + 7, size - 14, size - 14);
      }
    }
  }

  private click(pointer: Phaser.Input.Pointer): void {
    if (!this.world) return;
    const size: number = this.world.map.tile_size;
    const x: number = Math.floor(pointer.x / size);
    const y: number = Math.floor(pointer.y / size);
    if (x < 0 || y < 0 || x >= this.world.map.width || y >= this.world.map.height) return;
    if (this.editing) { this.callbacks.cell(x, y); return; }
    for (const [id, view] of this.visitors) {
      if (Math.hypot(pointer.x - view.container.x, pointer.y - view.container.y) <= size * 0.65) {
        this.callbacks.select(id);
        return;
      }
    }
  }

  private hover(pointer: Phaser.Input.Pointer): void {
    if (!this.world) return;
    const x: number = Math.floor(pointer.x / this.world.map.tile_size);
    const y: number = Math.floor(pointer.y / this.world.map.tile_size);
    const object: WorldObject | undefined = this.world.map.objects.find((item: WorldObject): boolean => x >= item.x && x < item.x + (item.width ?? 1) && y >= item.y && y < item.y + (item.height ?? 1));
    this.callbacks.hover(object ? `${object.name} · ${object.reserved_by ? "reserved" : "available"} · cell ${x}, ${y}` : `${this.editing ? "Click to toggle obstacle" : "Click a visitor to inspect"} · cell ${x}, ${y}`);
  }
}
