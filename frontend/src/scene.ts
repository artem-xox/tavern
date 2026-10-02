import Phaser from "phaser";
import { shippedPose, spriteOf, stills } from "./sprites";
import type { ActivityView, Actor, Cell, Verb, World, WorldObject } from "./types";

interface SceneCallbacks {
  select: (actorId: string) => void;
  cell: (x: number, y: number) => void;
  hover: (message: string) => void;
}

interface ActorView {
  container: Phaser.GameObjects.Container;
  sprite: Phaser.GameObjects.Image;
  name: Phaser.GameObjects.Text;
  status: Phaser.GameObjects.Text;
  selection: Phaser.GameObjects.Arc;
  mug: Phaser.GameObjects.Container;
  speech: Phaser.GameObjects.Text;
  targetX: number;
  targetY: number;
  cellX: number;
  cellY: number;
  direction: string;
}

/** Render server snapshots; interpolation changes display coordinates only. */
export class TavernScene extends Phaser.Scene {
  private world: World | null = null;
  private activities: Record<Verb, ActivityView> = {};
  private floor!: Phaser.GameObjects.Graphics;
  private hearthGlow!: Phaser.GameObjects.Graphics;
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

  /** Load four cardinal stills for every shipped pose of every character sprite. */
  preload(): void {
    for (const still of stills()) this.load.image(still.key, still.url);
  }

  /** Create rendering layers and map pointer events to server cell coordinates. */
  create(): void {
    for (const still of stills()) this.textures.get(still.key).setFilter(Phaser.Textures.FilterMode.NEAREST);
    this.floor = this.add.graphics();
    this.hearthGlow = this.add.graphics();
    this.furniture = this.add.graphics();
    this.labels = this.add.group();
    this.route = this.add.graphics();
    this.input.on("pointerdown", (pointer: Phaser.Input.Pointer): void => this.click(pointer));
    this.input.on("pointermove", (pointer: Phaser.Input.Pointer): void => this.hover(pointer));
    this.ready = true;
    if (this.world) this.setWorld(this.world, this.activities);
  }

  /** Apply a world snapshot, keeping authoritative actors separate from sprites. */
  setWorld(world: World, activities: Record<Verb, ActivityView>): void {
    const reset: boolean = this.world !== null && world.tick < this.world.tick;
    this.world = world;
    this.activities = activities;
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
  update(time: number, delta: number): void {
    const blend: number = 1 - Math.exp(-delta / 90);
    for (const view of this.visitors.values()) {
      view.container.x += (view.targetX - view.container.x) * blend;
      view.container.y += (view.targetY - view.container.y) * blend;
    }
    this.drawHearthGlow(time);
  }

  /** Let firelight flicker on the floor in front of each fireplace. */
  private drawHearthGlow(time: number): void {
    this.hearthGlow.clear();
    if (!this.world) return;
    const size: number = this.world.map.tile_size;
    const flicker: number = 0.82 + 0.1 * Math.sin(time / 170) + 0.08 * Math.sin(time / 53);
    for (const hearth of this.world.map.objects.filter((object: WorldObject): boolean => object.kind === "fireplace")) {
      // Light spills into the room on the side the fireplace opens to.
      const [dx, dy]: [number, number] = this.hearthFacing(hearth);
      const x: number = (hearth.x + (hearth.width ?? 1) / 2 + dx * 0.9) * size;
      const y: number = (hearth.y + (hearth.height ?? 1) / 2 + dy * 0.9) * size;
      for (let ring: number = 5; ring > 0; ring -= 1) {
        this.hearthGlow.fillStyle(0xf5a347, 0.045 * flicker).fillCircle(x, y, ring * size * 0.62 * flicker);
      }
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
    this.drawRugs(world, size);
    for (const [x, y] of blocked) this.drawWall(x * size, y * size, size);
    // Doors, windows and the fireplace sit inside the outer wall.
    for (const object of world.map.objects.filter((item: WorldObject): boolean => ["door", "window", "fireplace"].includes(item.kind))) {
      for (let dy: number = 0; dy < (object.height ?? 1); dy += 1) {
        for (let dx: number = 0; dx < (object.width ?? 1); dx += 1) this.drawWall((object.x + dx) * size, (object.y + dy) * size, size);
      }
    }
  }

  /** Which way a fireplace opens: away from the outer wall it is built into. */
  private hearthFacing(hearth: WorldObject): [number, number] {
    const map = this.world!.map;
    if (hearth.x === 0) return [1, 0];
    if (hearth.x + (hearth.width ?? 1) === map.width) return [-1, 0];
    return hearth.y === 0 ? [0, 1] : [0, -1];
  }

  /** Lay a rug under every table and its chairs, kept clear of the walls. */
  private drawRugs(world: World, size: number): void {
    const palette: [number, number][] = [[0x8d463a, 0xd2a367], [0x526455, 0xabbd92], [0x4b5874, 0xa9b6cf], [0x7b5b30, 0xd9b26b]];
    world.map.objects.filter((object: WorldObject): boolean => object.kind === "table").forEach((table: WorldObject, index: number): void => {
      const [fill, trim] = palette[index % palette.length]!;
      const x: number = (table.x - 1.2) * size;
      const y: number = (table.y - 0.3) * size;
      const width: number = ((table.width ?? 1) + 2.4) * size;
      const height: number = ((table.height ?? 1) + 0.6) * size;
      this.floor.fillStyle(0x2b211b, 0.35).fillRoundedRect(x - 2, y + 3, width + 4, height, 7);
      this.floor.fillStyle(fill).fillRoundedRect(x, y, width, height, 6);
      this.floor.lineStyle(2, trim, 0.55).strokeRoundedRect(x + 4, y + 4, width - 8, height - 8, 4);
      for (let col: number = 0; col < 6; col += 1) {
        const cx: number = x + (col + 0.5) * width / 6;
        this.floor.lineStyle(1, trim, 0.2).strokePoints([{ x: cx, y: y + height / 2 - 6 }, { x: cx + 6, y: y + height / 2 }, { x: cx, y: y + height / 2 + 6 }, { x: cx - 6, y: y + height / 2 }], true);
      }
    });
  }

  private drawRoomDetails(size: number): void {
    this.floor.fillStyle(0xb9afa0).fillRect(16 * size, size, 3 * size, 3 * size);
    for (let x: number = 16; x < 19; x += 1) {
      for (let y: number = 1; y < 4; y += 1) {
        this.floor.lineStyle(1, 0x777e72, 0.4).strokeRect(x * size, y * size, size, size);
        this.floor.fillStyle(0x667568, 0.25).fillRect((x + 0.45) * size, (y + 0.45) * size, 4, 4);
      }
    }
    this.floor.fillStyle(0xddd1aa, 0.35).fillRect(3.3 * size, 9.2 * size, 3, size * 0.6);
    for (const [x, y] of [[2, 2], [18, 7]]) {
      for (let radius: number = 3; radius > 0; radius -= 1) {
        this.floor.fillStyle(0xf5ce82, 0.025).fillCircle((x! + 0.5) * size, (y! + 0.5) * size, radius * size);
      }
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
    if (object.kind === "door") { this.drawDoor(object, size); return; }
    if (object.kind === "window") { this.drawWindow(object, size); return; }
    if (object.kind === "fireplace") { this.drawFireplace(object, size); return; }
    this.furniture.fillStyle(0x1e1914, 0.32);
    this.furniture.fillEllipse(x + ((object.width ?? 1) - 1) * size / 2, y + 10, size * (object.width ?? 1) * 0.9, 12);
    if (object.kind === "tap") this.drawTap(x, y);
    if (object.kind === "toilet") this.drawToilet(x, y);
    if (object.kind === "chair") this.drawChair(x, y, object.facing);
    if (object.kind === "bar") this.drawBar(object, size);
    if (object.kind === "table") { this.drawTable(object, size); this.appealLabel(object, size); }
    if (object.kind === "darts") this.drawDarts(x, y);
    if (object.reserved_by) this.furniture.lineStyle(2, 0xe6c88d, 0.75).strokeCircle(x, y, 15);
    if (["tap", "toilet", "darts"].includes(object.kind)) this.objectLabel(object, x, y);
  }

  private drawDoor(door: WorldObject, size: number): void {
    const x: number = (door.x - 0.3) * size;
    const y: number = door.y * size;
    this.floor.fillStyle(0x41372a).fillRoundedRect((door.x - 1) * size, (door.y - 1.2) * size, 3 * size, size * 0.7, 3);
    this.floor.lineStyle(1, 0xb29762, 0.6).strokeRoundedRect((door.x - 0.85) * size, (door.y - 1.1) * size, 2.7 * size, size * 0.5, 2);
    this.furniture.fillStyle(0x634835).fillRoundedRect(x, y + 1, 1.6 * size, 26, 3);
    for (let plank: number = 1; plank < 4; plank += 1) {
      this.furniture.lineStyle(1, 0xc0a16d, 0.5).lineBetween(x + plank * 0.4 * size, y + 5, x + plank * 0.4 * size, y + 25);
    }
    this.furniture.fillStyle(0xe2c27a).fillCircle(x + 1.6 * size - 9, y + 15, 2);
  }

  private drawWindow(pane: WorldObject, size: number): void {
    const x: number = pane.x * size;
    const y: number = pane.y * size;
    this.furniture.fillStyle(0x403e34).fillRoundedRect(x + 5, y + 3, 22, 26, 2);
    this.furniture.fillStyle(0x88a39c).fillRect(x + 9, y + 6, 14, 19);
    this.furniture.lineStyle(2, 0xd3b584).lineBetween(x + 16, y + 6, x + 16, y + 25);
    this.furniture.lineBetween(x + 9, y + 15, x + 23, y + 15);
    this.furniture.fillStyle(0xc7a272).fillRect(x + 6, y + 26, 23, 4);
  }

  private drawFireplace(hearth: WorldObject, size: number): void {
    const x: number = hearth.x * size;
    const y: number = hearth.y * size;
    const width: number = (hearth.width ?? 1) * size;
    const height: number = (hearth.height ?? 1) * size;
    const [dx, dy]: [number, number] = this.hearthFacing(hearth);
    // Stone surround in the wall, with a hearthstone lip on the room side.
    this.furniture.fillStyle(0x6d645b).fillRoundedRect(x - 3, y - 3, width + 6, height + 6, 4);
    this.furniture.lineStyle(1, 0x8d8378, 0.7).strokeRoundedRect(x, y, width, height, 3);
    this.furniture.fillStyle(0x857b70).fillRect(x + (dx < 0 ? -6 : dx > 0 ? width : 0), y + (dy < 0 ? -6 : dy > 0 ? height : 0),
      dx === 0 ? width : 6, dy === 0 ? height : 6);
    // Firebox with logs and layered flames.
    const cx: number = x + width / 2;
    const cy: number = y + height / 2;
    const span: number = Math.min(width, height) * 0.62;
    const reach: number = Math.max(width, height) * 0.7;
    this.furniture.fillStyle(0x1f1612).fillRoundedRect(cx - (dx === 0 ? reach : span) / 2, cy - (dy === 0 ? reach : span) / 2,
      dx === 0 ? reach : span, dy === 0 ? reach : span, 6);
    this.furniture.fillStyle(0x5a3b25).fillRoundedRect(cx - 9, cy - 3, 18, 6, 2);
    this.furniture.fillStyle(0xe2763a).fillEllipse(cx - 3, cy - 1, 14, 20);
    this.furniture.fillStyle(0xf09a3e).fillEllipse(cx + 4, cy - 2, 11, 16);
    this.furniture.fillStyle(0xf8d06a).fillEllipse(cx, cy, 7, 11);
  }

  /** Show how appealing a table's seats are, and why. */
  private appealLabel(table: WorldObject, size: number): void {
    if (table.appeal === undefined) return;
    const reasons: Record<string, string> = { fireplace: "fire", window: "window" };
    const why: string = (table.comforts ?? []).map((comfort: string): string => reasons[comfort] ?? comfort).join(" · ");
    const label: Phaser.GameObjects.Text = this.add.text((table.x + (table.width ?? 1) / 2) * size, (table.y + (table.height ?? 1) + 0.42) * size,
      `appeal ${table.appeal.toFixed(1)}${why ? ` · ${why}` : ""}`, {
        fontFamily: "system-ui, sans-serif", fontSize: "8px", color: "#f3e3c3", backgroundColor: "#2b221cc0", padding: { x: 4, y: 1 },
      }).setOrigin(0.5, 0.5);
    this.labels.add(label);
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
    const shadow: Phaser.GameObjects.Ellipse = this.add.ellipse(0, 9, 25, 12, 0x191815, 0.4);
    const selection: Phaser.GameObjects.Arc = this.add.circle(0, 0, 16).setStrokeStyle(2, 0xffe0a3).setVisible(actor.id === this.selectedId);
    const { name: character, sheet } = spriteOf(actor);
    const sprite: Phaser.GameObjects.Image = this.add.image(0, sheet.lift, `${character}-Idle-south`).setDisplaySize(sheet.size, sheet.size);
    const name: Phaser.GameObjects.Text = this.add.text(0, -53, actor.name, { fontFamily: "system-ui", fontSize: "11px", color: "#fff4dc", stroke: "#322b24", strokeThickness: 3 }).setOrigin(0.5);
    const status: Phaser.GameObjects.Text = this.add.text(0, 22, actor.status, { fontFamily: "system-ui", fontSize: "9px", color: "#ead6b6", backgroundColor: "#302b25b0", padding: { x: 3, y: 1 } }).setOrigin(0.5);
    const mugBody: Phaser.GameObjects.Rectangle = this.add.rectangle(0, 0, 7, 10, 0xd6a252);
    const foam: Phaser.GameObjects.Ellipse = this.add.ellipse(0, -5, 8, 4, 0xffebc2);
    const mug: Phaser.GameObjects.Container = this.add.container(12, 3, [mugBody, foam]);
    const speech: Phaser.GameObjects.Text = this.add.text(0, -70, "", { fontFamily: "Georgia", fontSize: "10px", color: "#48392b", backgroundColor: "#f4e6c6", padding: { x: 6, y: 4 } }).setOrigin(0.5).setVisible(false);
    const container: Phaser.GameObjects.Container = this.add.container(0, 0, [shadow, selection, sprite, name, status, mug, speech]);
    return { container, sprite, name, status, selection, mug, speech, targetX: 0, targetY: 0, cellX: actor.x, cellY: actor.y, direction: "south" };
  }

  private updateVisitor(view: ActorView, actor: Actor, size: number, reset: boolean): void {
    const seat: WorldObject | undefined = this.world?.map.objects.find((object: WorldObject): boolean => object.id === actor.seat_id);
    const target: WorldObject | undefined = this.world?.map.objects.find((object: WorldObject): boolean => object.id === actor.action?.target_id);
    view.direction = actor.x > view.cellX ? "east" : actor.x < view.cellX ? "west" : actor.y > view.cellY ? "south" : actor.y < view.cellY ? "north" : view.direction;
    if (actor.status !== "walking") {
      view.direction = seat?.facing ?? (target && actor.status === "interacting" ? this.facingTarget(actor, target, view.direction) : view.direction);
    }
    const { name: character, sheet } = spriteOf(actor);
    const pose: string = shippedPose(sheet, this.actorPose(actor));
    const texture: string = `${character}-${pose}-${view.direction}`;
    if (view.sprite.texture.key !== texture) view.sprite.setTexture(texture);
    view.sprite.setDisplaySize(sheet.size, sheet.size);
    view.sprite.setY(sheet.lift + (pose === "Seated" || pose === "Bathroom" ? 3 : 0));
    view.cellX = actor.x;
    view.cellY = actor.y;
    const x: number = (actor.x + 0.5) * size;
    const y: number = (actor.y + 0.5) * size;
    if (reset || view.targetX === 0 || Math.hypot(x - view.container.x, y - view.container.y) > size * 3) view.container.setPosition(x, y);
    view.targetX = x;
    view.targetY = y;
    view.name.setText(actor.name);
    const incoming: Actor | undefined = this.world?.actors.find((visitor: Actor): boolean => visitor.action?.verb === "talk" && visitor.action.target_id === actor.id);
    const chatting: boolean = !!incoming || actor.action?.verb === "talk";
    const label = (verb: Verb): string | undefined => (verb === "watch" && target?.kind === "fireplace" ? "by the fire" : this.activities[verb]?.status ?? undefined);
    view.status.setText(actor.status === "walking" ? `→ ${label(actor.action?.verb ?? "") ?? "exploring"}` : chatting ? "chatting" : actor.action ? label(actor.action.verb) ?? actor.action.verb : actor.seat_id ? "seated" : "thinking");
    view.mug.setVisible(actor.inventory.beer > 0 && pose !== "Drinking" && pose !== "TakeBeer");
    view.speech.setVisible(chatting);
    view.speech.setText(incoming ? "Quite a story!" : "News from the road…");
    view.container.setDepth(10 + y / 1000);
  }

  private actorPose(actor: Actor): string {
    if (actor.status === "walking") return "Walking";
    const pose: string | null | undefined = actor.action ? this.activities[actor.action.verb]?.pose : null;
    if (actor.status === "interacting" && pose) return pose;
    return actor.seat_id ? "Seated" : "Idle";
  }

  private facingTarget(actor: Actor, target: WorldObject, fallback: string): string {
    const dx: number = target.x + (target.width ?? 1) / 2 - (actor.x + 0.5);
    const dy: number = target.y + (target.height ?? 1) / 2 - (actor.y + 0.5);
    if (Math.abs(dx) >= Math.abs(dy) && dx !== 0) return dx > 0 ? "east" : "west";
    if (dy !== 0) return dy > 0 ? "south" : "north";
    return fallback;
  }

  private drawRoute(): void {
    this.route.clear();
    if (!this.world) return;
    const size: number = this.world.map.tile_size;
    this.drawOwnSeats(size);
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

  /** Mark each visitor's own seat with a ribbon in their colour, so a taken seat is visible. */
  private drawOwnSeats(size: number): void {
    for (const actor of this.world?.actors ?? []) {
      const seat: WorldObject | undefined = this.world?.map.objects.find((object: WorldObject): boolean => object.id === actor.favorite_seat_id);
      if (!seat) continue;
      const color: number = Phaser.Display.Color.ValueToColor(actor.color).color;
      const x: number = (seat.x + (seat.facing === "west" ? 0.82 : 0.18)) * size;
      const y: number = (seat.y + 0.2) * size;
      this.route.fillStyle(0x221b16, 0.8).fillCircle(x, y, 4.5);
      this.route.fillStyle(color).fillCircle(x, y, 3.2);
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
    const owner: Actor | undefined = this.world.actors.find((actor: Actor): boolean => !!object && actor.favorite_seat_id === object.id);
    const details: string = object?.appeal !== undefined ? ` · appeal ${object.appeal.toFixed(2)}${object.comforts?.length ? ` (${object.comforts.join(", ")})` : ""}` : "";
    this.callbacks.hover(object ? `${object.name} · ${object.reserved_by ? "reserved" : "available"}${owner ? ` · ${owner.name}'s seat` : ""}${details} · cell ${x}, ${y}` : `${this.editing ? "Click to toggle obstacle" : "Click a visitor to inspect"} · cell ${x}, ${y}`);
  }
}
