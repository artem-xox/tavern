import Phaser from "phaser";
import { placeBubble } from "./bubble";
import { drawBar, drawChair, drawDarts, drawDoor, drawFireplace, drawRugs, drawTable, drawTap, drawToilet, drawWindow, hearthFacing } from "./furniture";
import { shippedPose, spriteOf, stills } from "./sprites";
import type { ActivityView, Actor, Cell, Conversation, EmoteKind, Mind, Turn, Verb, World, WorldObject } from "./types";

/** Speech bubbles wrap at this many pixels and draw above every guest. */
const BUBBLE_WRAP = 180;
const BUBBLE_DEPTH = 1000;

/** Glyph and colour of each emote above a visitor's head. */
const EMOTE_GLYPHS: Record<EmoteKind, [string, string]> = {
  alert: ["!", "#c0392b"], confused: ["?", "#2e6f9e"], angry: ["✹", "#b03a2e"],
  affection: ["♥", "#c2457a"], sleep: ["z", "#5b6c8f"], waiting: ["…", "#6b5a45"],
};

interface SceneCallbacks {
  select: (actorId: string) => void;
  cell: (x: number, y: number) => void;
  hover: (message: string) => void;
}

interface ActorView {
  container: Phaser.GameObjects.Container;
  sprite: Phaser.GameObjects.Image;
  name: Phaser.GameObjects.Text;
  selection: Phaser.GameObjects.Arc;
  mug: Phaser.GameObjects.Container;
  speech: Phaser.GameObjects.Text;
  emote: Phaser.GameObjects.Text;
  targetX: number;
  targetY: number;
  cellX: number;
  cellY: number;
  direction: string;
  /** How far drink sways the sprite, 0–1, as the server derives it. */
  sway: number;
}

/** Render server snapshots; interpolation changes display coordinates only. */
export class TavernScene extends Phaser.Scene {
  private world: World | null = null;
  private activities: Record<Verb, ActivityView> = {};
  private minds: Record<string, Mind> = {};
  private floor!: Phaser.GameObjects.Graphics;
  private hearthGlow!: Phaser.GameObjects.Graphics;
  private furniture!: Phaser.GameObjects.Graphics;
  private route!: Phaser.GameObjects.Graphics;
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
    this.route = this.add.graphics();
    this.input.on("pointerdown", (pointer: Phaser.Input.Pointer): void => this.click(pointer));
    this.input.on("pointermove", (pointer: Phaser.Input.Pointer): void => this.hover(pointer));
    this.ready = true;
    if (this.world) this.setWorld(this.world, this.activities, this.minds);
  }

  /** Apply a world snapshot, keeping authoritative actors separate from sprites. */
  setWorld(world: World, activities: Record<Verb, ActivityView>, minds: Record<string, Mind>): void {
    const reset: boolean = this.world !== null && world.tick < this.world.tick;
    this.world = world;
    this.activities = activities;
    this.minds = minds;
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
      // Drunk guests sway; each at their own pace, so a table of drinkers does not rock in step.
      view.sprite.setAngle(view.sway * 8 * Math.sin(time / 420 + view.cellX * 1.7 + view.cellY));
      this.placeSpeech(view);
    }
    this.drawHearthGlow(time);
  }

  /** Keep a speech bubble over its speaker, inside the map and above the other guests. */
  private placeSpeech(view: ActorView): void {
    if (!view.speech.visible) return;
    const placement = placeBubble(view.container.x, view.container.y, view.speech.width, view.speech.height, this.scale);
    view.speech.setOrigin(0.5, placement.originY).setPosition(placement.x, placement.y);
  }

  /** Let firelight flicker on the floor in front of each fireplace. */
  private drawHearthGlow(time: number): void {
    this.hearthGlow.clear();
    if (!this.world) return;
    const size: number = this.world.map.tile_size;
    const flicker: number = 0.82 + 0.1 * Math.sin(time / 170) + 0.08 * Math.sin(time / 53);
    for (const hearth of this.world.map.objects.filter((object: WorldObject): boolean => object.kind === "fireplace")) {
      // Light spills into the room on the side the fireplace opens to.
      const [dx, dy]: [number, number] = hearthFacing(hearth, this.world.map.width);
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
    drawRugs(this.floor, world.map.objects, size);
    for (const [x, y] of blocked) this.drawWall(x * size, y * size, size);
    // Doors, windows and the fireplace sit inside the outer wall.
    for (const object of world.map.objects.filter((item: WorldObject): boolean => ["door", "window", "fireplace"].includes(item.kind))) {
      for (let dy: number = 0; dy < (object.height ?? 1); dy += 1) {
        for (let dx: number = 0; dx < (object.width ?? 1); dx += 1) this.drawWall((object.x + dx) * size, (object.y + dy) * size, size);
      }
    }
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
    if (object.kind === "door") { drawDoor(this.furniture, this.floor, object, size); return; }
    if (object.kind === "window") { drawWindow(this.furniture, object, size); return; }
    if (object.kind === "fireplace") { drawFireplace(this.furniture, object, size, this.world!.map.width); return; }
    this.furniture.fillStyle(0x1e1914, 0.32);
    this.furniture.fillEllipse(x + ((object.width ?? 1) - 1) * size / 2, y + 10, size * (object.width ?? 1) * 0.9, 12);
    if (object.kind === "tap") drawTap(this.furniture, x, y);
    if (object.kind === "toilet") drawToilet(this.furniture, x, y);
    if (object.kind === "chair") drawChair(this.furniture, x, y, object.facing);
    if (object.kind === "bar") drawBar(this.furniture, object, size);
    if (object.kind === "table") { drawTable(this.furniture, object, size); }
    if (object.kind === "darts") drawDarts(this.furniture, x, y);
    if (object.reserved_by) this.furniture.lineStyle(2, 0xe6c88d, 0.75).strokeCircle(x, y, 15);
  }

  private syncVisitors(world: World, reset: boolean): void {
    const ids: Set<string> = new Set(world.actors.map((actor: Actor): string => actor.id));
    for (const [id, view] of this.visitors) {
      if (!ids.has(id)) { view.container.destroy(); view.speech.destroy(); this.visitors.delete(id); }
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
    const mugBody: Phaser.GameObjects.Rectangle = this.add.rectangle(0, 0, 7, 10, 0xd6a252);
    const foam: Phaser.GameObjects.Ellipse = this.add.ellipse(0, -5, 8, 4, 0xffebc2);
    const mug: Phaser.GameObjects.Container = this.add.container(12, 3, [mugBody, foam]);
    // Outside the container, so it can sit above every guest and be kept inside the map each frame.
    const speech: Phaser.GameObjects.Text = this.add.text(0, 0, "", { fontFamily: "Georgia", fontSize: "12px", color: "#48392b", backgroundColor: "#f4e6c6", align: "center", lineSpacing: 3, padding: { x: 8, y: 5 }, wordWrap: { width: BUBBLE_WRAP, useAdvancedWrap: true } }).setOrigin(0.5, 1).setDepth(BUBBLE_DEPTH).setVisible(false);
    const emote: Phaser.GameObjects.Text = this.add.text(17, -44, "", { fontFamily: "system-ui", fontSize: "12px", fontStyle: "bold", backgroundColor: "#f4e6c6", padding: { x: 4, y: 1 } }).setOrigin(0.5).setVisible(false);
    const container: Phaser.GameObjects.Container = this.add.container(0, 0, [shadow, selection, sprite, name, mug, emote]);
    return { container, sprite, name, selection, mug, speech, emote, targetX: 0, targetY: 0, cellX: actor.x, cellY: actor.y, direction: "south", sway: 0 };
  }

  private updateVisitor(view: ActorView, actor: Actor, size: number, reset: boolean): void {
    const seat: WorldObject | undefined = this.world?.map.objects.find((object: WorldObject): boolean => object.id === actor.seat_id);
    const target: WorldObject | undefined = this.world?.map.objects.find((object: WorldObject): boolean => object.id === actor.action?.target_id);
    view.direction = actor.x > view.cellX ? "east" : actor.x < view.cellX ? "west" : actor.y > view.cellY ? "south" : actor.y < view.cellY ? "north" : view.direction;
    if (actor.status !== "walking") {
      // The server turns heads toward sounds and partners; otherwise the seat or the task decides.
      view.direction = actor.facing ?? seat?.facing ?? (target && actor.status === "interacting" ? this.facingTarget(actor, target, view.direction) : view.direction);
    }
    const { name: character, sheet } = spriteOf(actor);
    const pose: string = shippedPose(sheet, this.actorPose(actor));
    const texture: string = `${character}-${pose}-${view.direction}`;
    if (view.sprite.texture.key !== texture) view.sprite.setTexture(texture);
    view.sprite.setDisplaySize(sheet.size, sheet.size);
    view.sprite.setY(sheet.lift + (pose === "Seated" || pose === "Bathroom" || pose === "DrinkingSeated" || pose === "TalkingSeated" ? 3 : 0));
    view.cellX = actor.x;
    view.cellY = actor.y;
    const x: number = (actor.x + 0.5) * size;
    const y: number = (actor.y + 0.5) * size;
    if (reset || view.targetX === 0 || Math.hypot(x - view.container.x, y - view.container.y) > size * 3) view.container.setPosition(x, y);
    view.targetX = x;
    view.targetY = y;
    view.name.setText(actor.name);
    view.sway = this.minds[actor.id]?.sway ?? 0;
    // The bubble shows the scene's latest line over its speaker until the next one is spoken.
    const scene: Conversation | undefined = this.world?.conversations.find((item: Conversation): boolean => item.participants.includes(actor.id));
    const line: Turn | undefined = scene?.turns[scene.turns.length - 1];
    const chatting: boolean = scene !== undefined;
    view.mug.setVisible(actor.inventory.beer > 0 && pose !== "Drinking" && pose !== "DrinkingSeated" && pose !== "TakeBeer");
    view.speech.setVisible(line?.speaker === actor.id);
    view.speech.setText(line?.line ?? "");
    this.showEmote(view, actor);
    view.container.setDepth(10 + y / 1000);
  }

  private showEmote(view: ActorView, actor: Actor): void {
    view.emote.setVisible(actor.emote !== null);
    if (actor.emote === null) return;
    const [glyph, color] = EMOTE_GLYPHS[actor.emote.kind];
    view.emote.setText(glyph).setColor(color);
  }

  private actorPose(actor: Actor): string {
    if (actor.status === "walking") return "Walking";
    const pose: string | null | undefined = actor.action ? this.activities[actor.action.verb]?.pose : null;
    if (actor.status === "interacting" && pose) {
      if (actor.seat_id && pose === "Drinking") return "DrinkingSeated";
      return actor.seat_id && pose === "Talking" ? "TalkingSeated" : pose;
    }
    const chatting: boolean = this.world?.conversations.some((scene: Conversation): boolean => scene.participants.includes(actor.id)) ?? false;
    return actor.seat_id ? chatting ? "TalkingSeated" : "Seated" : "Idle";
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
    const stock: string = object?.kind === "tap" ? ` · ${object.stock ?? 0} left` : "";
    const details: string = stock + (object?.appeal !== undefined ? ` · appeal ${object.appeal.toFixed(2)}${object.comforts?.length ? ` (${object.comforts.join(", ")})` : ""}` : "");
    this.callbacks.hover(object ? `${object.name} · ${object.reserved_by ? "reserved" : "available"}${owner ? ` · ${owner.name}'s seat` : ""}${details} · cell ${x}, ${y}` : `${this.editing ? "Click to toggle obstacle" : "Click a visitor to inspect"} · cell ${x}, ${y}`);
  }
}
