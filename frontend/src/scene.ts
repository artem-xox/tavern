import Phaser from "phaser";
import { chunkAt, placeBubble, splitLine } from "./bubble";
import { RoomArt } from "./room-art";
import { shippedPose, spriteOf, stills } from "./sprites";
import type { ActivityView, Actor, Cell, Conversation, EmoteKind, Mind, Turn, Verb, World, WorldObject } from "./types";

/** Speech bubbles wrap at this many pixels and draw above every guest. */
const BUBBLE_WRAP = 150;
const BUBBLE_FILL = 0xf4e6c6;
const BUBBLE_EDGE = 0x6b5640;
/** Length and half-width of a bubble's pointer, and how far from a corner its tip stays. */
const TAIL = 7;
const TAIL_HALF = 6;
const TAIL_INSET = 14;
const BUBBLE_DEPTH = 1000;
/** Even a sober guest fidgets a little; drink adds to it. */
const IDLE_SWAY = 0.12;

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
  speech: Phaser.GameObjects.Container;
  speechBox: Phaser.GameObjects.Graphics;
  speechText: Phaser.GameObjects.Text;
  /** The line being told in pieces, and when it began. */
  talk: { key: string; chunks: string[]; start: number } | null;
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
  private readonly roomArt: RoomArt;
  private route!: Phaser.GameObjects.Graphics;
  private readonly visitors: Map<string, ActorView> = new Map();
  private selectedId: string | null = null;
  private editing: boolean = false;
  private ready: boolean = false;

  constructor(private readonly callbacks: SceneCallbacks) {
    super("tavern");
    this.roomArt = new RoomArt(this);
  }

  /** Load four cardinal stills for every shipped pose of every character sprite. */
  preload(): void {
    for (const still of stills()) this.load.image(still.key, still.url);
    this.roomArt.preload();
  }

  /** Create rendering layers and map pointer events to server cell coordinates. */
  create(): void {
    for (const still of stills()) this.textures.get(still.key).setFilter(Phaser.Textures.FilterMode.NEAREST);
    this.roomArt.create();
    this.route = this.add.graphics().setDepth(5);
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
      // Everyone fidgets and drunk guests sway more; each at their own pace, so a table of drinkers does not rock in step.
      view.sprite.setAngle(Math.max(view.sway, IDLE_SWAY) * 8 * Math.sin(time / 420 + view.cellX * 1.7 + view.cellY));
      this.placeSpeech(view);
    }
    this.roomArt.update(time);
  }

  /** Show the piece of the line now due in a bubble over its speaker, inside the map and above the other guests. */
  private placeSpeech(view: ActorView): void {
    const now: number = this.time.now;
    view.speech.setVisible(view.talk !== null);
    if (!view.talk) return;
    const piece: string = view.talk.chunks[chunkAt(view.talk.chunks, now - view.talk.start)]!;
    if (view.speechText.text !== piece) view.speechText.setText(piece);
    const { width, height } = view.speechText;
    const placement = placeBubble(view.container.x, view.container.y, width, height, this.scale);
    view.speech.setPosition(placement.x, placement.y);
    this.drawBubble(view, width, height, placement.originY, view.container.x - placement.x);
  }

  /** Draw the bubble's body around its text, with a pointer toward the speaker at `speakerDx` from its centre. */
  private drawBubble(view: ActorView, width: number, height: number, originY: 0 | 1, speakerDx: number): void {
    const top: number = originY === 1 ? -height : 0;
    const down: number = originY === 1 ? 1 : -1;
    const tailX: number = Math.min(Math.max(speakerDx, -width / 2 + TAIL_INSET), width / 2 - TAIL_INSET);
    const baseY: number = originY === 1 ? top + height : top;
    const box: Phaser.GameObjects.Graphics = view.speechBox.clear();
    box.fillStyle(BUBBLE_FILL).fillRoundedRect(-width / 2, top, width, height, 9);
    box.lineStyle(2, BUBBLE_EDGE).strokeRoundedRect(-width / 2, top, width, height, 9);
    box.fillStyle(BUBBLE_FILL).fillRect(tailX - TAIL_HALF + 1, baseY - 1, 2 * TAIL_HALF - 2, 2);
    box.fillTriangle(tailX - TAIL_HALF, baseY, tailX + TAIL_HALF, baseY, tailX, baseY + down * TAIL);
    box.lineBetween(tailX - TAIL_HALF, baseY, tailX, baseY + down * TAIL);
    box.lineBetween(tailX + TAIL_HALF, baseY, tailX, baseY + down * TAIL);
    view.speechText.setY(top);
  }

  private renderMap(world: World): void {
    this.roomArt.render(world);
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
    // Outside the container, so it can sit above every guest and be kept inside the map each frame.
    const speechBox: Phaser.GameObjects.Graphics = this.add.graphics();
    const speechText: Phaser.GameObjects.Text = this.add.text(0, 0, "", { fontFamily: "Georgia", fontSize: "11px", color: "#48392b", align: "center", lineSpacing: 2, padding: { x: 9, y: 6 }, wordWrap: { width: BUBBLE_WRAP, useAdvancedWrap: true } }).setOrigin(0.5, 0);
    const speech: Phaser.GameObjects.Container = this.add.container(0, 0, [speechBox, speechText]).setDepth(BUBBLE_DEPTH).setVisible(false);
    const emote: Phaser.GameObjects.Text = this.add.text(17, -44, "", { fontFamily: "system-ui", fontSize: "12px", fontStyle: "bold", backgroundColor: "#f4e6c6", padding: { x: 4, y: 1 } }).setOrigin(0.5).setVisible(false);
    const container: Phaser.GameObjects.Container = this.add.container(0, 0, [shadow, selection, sprite, name, emote]);
    return { container, sprite, name, selection, speech, speechBox, speechText, talk: null, emote, targetX: 0, targetY: 0, cellX: actor.x, cellY: actor.y, direction: "south", sway: 0 };
  }

  private updateVisitor(view: ActorView, actor: Actor, size: number, reset: boolean): void {
    const seat: WorldObject | undefined = this.world?.map.objects.find((object: WorldObject): boolean => object.id === actor.seat_id);
    const target: WorldObject | undefined = this.world?.map.objects.find((object: WorldObject): boolean => object.id === actor.action?.target_id);
    view.direction = actor.x > view.cellX ? "east" : actor.x < view.cellX ? "west" : actor.y > view.cellY ? "south" : actor.y < view.cellY ? "north" : view.direction;
    if (actor.status !== "walking") {
      // The server turns heads toward sounds and partners; otherwise the seat or the task decides.
      view.direction = actor.facing ?? seat?.facing ?? (target && actor.status === "interacting" ? target.facing ?? this.facingTarget(actor, target, view.direction) : view.direction);
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
    this.tellLine(view, actor);
    this.showEmote(view, actor);
    view.container.setDepth(10 + y / 1000);
  }

  /** Tell the scene's latest line over its speaker in pieces; the server keeps the scene up while the last one is heard. */
  private tellLine(view: ActorView, actor: Actor): void {
    const scene: Conversation | undefined = this.world?.conversations.find((item: Conversation): boolean => item.participants.includes(actor.id));
    const line: Turn | undefined = scene?.turns[scene.turns.length - 1];
    if (line?.speaker !== actor.id) { view.talk = null; return; }
    const key: string = `${line.time}:${line.line}`;
    if (view.talk?.key !== key) view.talk = { key, chunks: splitLine(line.line), start: this.time.now };
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
    const players: string = object?.game ? ` · ${object.game.players.map((id: string): string => this.world?.actors.find((actor: Actor): boolean => actor.id === id)?.name ?? id).join(" and ")} playing` : "";
    const details: string = stock + players + (object?.appeal !== undefined ? ` · appeal ${object.appeal.toFixed(2)}${object.comforts?.length ? ` (${object.comforts.join(", ")})` : ""}` : "");
    this.callbacks.hover(object ? `${object.name} · ${object.reserved_by ? "reserved" : "available"}${owner ? ` · ${owner.name}'s seat` : ""}${details} · cell ${x}, ${y}` : `${this.editing ? "Click to toggle obstacle" : "Click a visitor to inspect"} · cell ${x}, ${y}`);
  }
}
