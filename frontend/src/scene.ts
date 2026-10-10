import Phaser from "phaser";
import { callout, newer } from "./bubble";
import { drawCandles, drawSconces } from "./candles";
import { EMOTE_KINDS, EMOTE_WORDS, emoteFrame, emoteFrames, emoteMotion, emotePalette } from "./emotes";
import { fightPose } from "./fightview";
import { drawFloor } from "./floor";
import { drawBar, drawChair, drawDarts, drawDiceTable, drawDoor, drawTable, drawTap, drawToilet, drawWindow } from "./furniture";
import { drawFireplace, drawFlames, drawHearthGlow } from "./hearth";
import { mapParts, type MapParts } from "./mapview";
import { Speech } from "./speech";
import { shippedPose, spriteOf, stills } from "./sprites";
import type { ActivityView, Actor, Cell, Conversation, EmoteKind, Mind, Turn, Verb, World, WorldObject } from "./types";
import { animateWounds, createWounds, makeCudgelTexture, readWounds, type Wounds } from "./woundview";

/** The seated version of a standing pose, for a visitor who does it from their seat. */
const SEATED_POSES: Readonly<Record<string, string>> = { Drinking: "DrinkingSeated", Talking: "TalkingSeated", Giving: "GivingSeated", Receiving: "ReceivingSeated" };
/** Poses drawn low on the cell, as a seated figure sits. */
const LOW_POSES: readonly string[] = ["Seated", "SleepingSeated", "Bathroom", "HurtSeated", "KnockedOut", ...Object.values(SEATED_POSES)];
/** Even a sober guest fidgets a little; drink adds to it. */
const IDLE_SWAY = 0.12;

/** Where an emote floats, in the guest's own coordinates: centred above their name. */
const EMOTE_Y = -72;

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
  speech: Speech;
  emote: Phaser.GameObjects.Image;
  /** The kind of emote showing and when it appeared, for its pop-in; null when none. */
  emoteKind: EmoteKind | null;
  emoteSince: number;
  targetX: number;
  targetY: number;
  cellX: number;
  cellY: number;
  direction: string;
  /** How far drink sways the sprite, 0–1, as the server derives it. */
  sway: number;
  /** A fight's and a wound's marks on the figure: the cudgel in hand, stars, lunge and tint. */
  wounds: Wounds;
}

/** Render server snapshots; interpolation changes display coordinates only. */
export class TavernScene extends Phaser.Scene {
  private world: World | null = null;
  private activities: Record<Verb, ActivityView> = {};
  private minds: Record<string, Mind> = {};
  private floor!: Phaser.GameObjects.Graphics;
  private hearthGlow!: Phaser.GameObjects.Graphics;
  private furniture!: Phaser.GameObjects.Graphics;
  /** Flames and sparks, above the furniture and redrawn every frame. */
  private flames!: Phaser.GameObjects.Graphics;
  /** The wall candles' flames and glow, redrawn every frame like the fire. */
  private candles!: Phaser.GameObjects.Graphics;
  private route!: Phaser.GameObjects.Graphics;
  private readonly visitors: Map<string, ActorView> = new Map();
  /** The fingerprints of the map as drawn; empty before the first snapshot, so everything draws once. */
  private drawn: MapParts = { size: "", floor: "", furniture: "" };
  private selectedId: string | null = null;
  private editing: boolean = false;
  private ready: boolean = false;

  constructor(private readonly callbacks: SceneCallbacks) {
    super("tavern");
  }

  /** Load all eight directional stills for every shipped pose of every character sprite. */
  preload(): void {
    for (const still of stills()) this.load.image(still.key, still.url);
  }

  /** Create rendering layers and map pointer events to server cell coordinates. */
  create(): void {
    for (const still of stills()) this.textures.get(still.key).setFilter(Phaser.Textures.FilterMode.NEAREST);
    this.makeEmoteTextures();
    makeCudgelTexture(this);
    this.floor = this.add.graphics();
    this.hearthGlow = this.add.graphics();
    this.furniture = this.add.graphics();
    this.flames = this.add.graphics();
    this.candles = this.add.graphics();
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
      animateWounds(view.wounds, view.sprite, Math.max(view.sway, IDLE_SWAY) * 8 * Math.sin(time / 420 + view.cellX * 1.7 + view.cellY), time, view.direction);
      this.animateEmote(view, time);
      view.speech.place(view.container.x, view.container.y, this.time.now, this.scale);
    }
    if (this.world) {
      const { objects, width, tile_size: size } = this.world.map;
      drawHearthGlow(this.hearthGlow, objects, width, size, time);
      drawFlames(this.flames, objects, width, size, time);
      drawCandles(this.candles, width, size, time);
    }
  }

  private renderMap(world: World): void {
    const parts: MapParts = mapParts(world.map);
    // Resizing reallocates the canvas buffer, even to the same size, so only a new size resizes it.
    if (parts.size !== this.drawn.size) this.scale.resize(world.map.width * world.map.tile_size, world.map.height * world.map.tile_size);
    if (parts.floor !== this.drawn.floor) drawFloor(this.floor, world);
    if (parts.furniture !== this.drawn.furniture) {
      this.furniture.clear();
      for (const object of world.map.objects) this.drawObject(object, world.map.tile_size);
      drawSconces(this.furniture, world.map.width, world.map.tile_size);
    }
    this.drawn = parts;
  }

  private drawObject(object: WorldObject, size: number): void {
    const x: number = (object.x + 0.5) * size;
    const y: number = (object.y + 0.5) * size;
    if (object.kind === "door") { drawDoor(this.furniture, object, size); return; }
    if (object.kind === "window") { drawWindow(this.furniture, object, size); return; }
    if (object.kind === "fireplace") { drawFireplace(this.furniture, object, size, this.world!.map.width); return; }
    this.furniture.fillStyle(0x1e1914, 0.32);
    this.furniture.fillEllipse(x + ((object.width ?? 1) - 1) * size / 2, y + 10, size * (object.width ?? 1) * 0.9, 12);
    if (object.kind === "tap") drawTap(this.furniture, x, y);
    if (object.kind === "toilet") drawToilet(this.furniture, x, y);
    if (object.kind === "chair" || object.kind === "dice_chair") drawChair(this.furniture, x, y, object.facing);
    if (object.kind === "bar") drawBar(this.furniture, object, size);
    if (object.kind === "table") { drawTable(this.furniture, object, size); }
    if (object.kind === "dice_table") drawDiceTable(this.furniture, object, size);
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
    const speech: Speech = new Speech(this);
    const emote: Phaser.GameObjects.Image = this.add.image(0, EMOTE_Y, "emote-alert-0").setVisible(false);
    const wounds: Wounds = createWounds(this, sheet.lift);
    const container: Phaser.GameObjects.Container = this.add.container(0, 0, [shadow, selection, sprite, wounds.cudgel, name, emote, ...wounds.stars]);
    return { container, sprite, name, selection, speech, emote, emoteKind: null, emoteSince: 0, targetX: 0, targetY: 0, cellX: actor.x, cellY: actor.y, direction: "south", sway: 0, wounds };
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
    let wanted: string = this.actorPose(actor);
    // A hurt guest on the move walks bent, or simply limps in their usual walk while the bent pose is not drawn yet.
    if (wanted === "Hurt" && actor.status === "walking" && !sheet.poses.includes("Hurt")) wanted = "Walking";
    const pose: string = shippedPose(sheet, wanted);
    const texture: string = `${character}-${pose}-${view.direction}`;
    if (view.sprite.texture.key !== texture) view.sprite.setTexture(texture);
    view.sprite.setDisplaySize(sheet.size, sheet.size);
    view.wounds.baseY = sheet.lift + (LOW_POSES.includes(pose) ? 3 : 0);
    readWounds(view.wounds, view.container, actor, this.world?.fights ?? [], this.world?.time ?? 0, wanted, pose, view.direction);
    view.cellX = actor.x;
    view.cellY = actor.y;
    const x: number = (actor.x + 0.5) * size;
    const y: number = (actor.y + 0.5) * size;
    if (reset || view.targetX === 0 || Math.hypot(x - view.container.x, y - view.container.y) > size * 3) view.container.setPosition(x, y);
    view.targetX = x;
    view.targetY = y;
    view.name.setText(actor.name);
    view.sway = this.minds[actor.id]?.sway ?? 0;
    const talk: Conversation | undefined = this.world?.conversations.find((item: Conversation): boolean => item.participants.includes(actor.id));
    const turn: Turn | undefined = talk?.turns[talk.turns.length - 1];
    view.speech.tell(newer(turn?.speaker === actor.id ? turn : null, callout(this.world?.events ?? [], actor.id, this.world?.time ?? 0)), this.time.now);
    this.showEmote(view, actor);
    view.container.setDepth(10 + y / 1000);
  }

  private showEmote(view: ActorView, actor: Actor): void {
    view.emote.setVisible(actor.emote !== null);
    if (actor.emote === null) { view.emoteKind = null; return; }
    if (view.emoteKind !== actor.emote.kind) { view.emoteKind = actor.emote.kind; view.emoteSince = this.time.now; }
  }

  /** Pop the emote in, bob it, and step its frames; kept inside the map's top edge. */
  private animateEmote(view: ActorView, time: number): void {
    if (view.emoteKind === null) return;
    const motion = emoteMotion(view.emoteKind, time - view.emoteSince, time);
    view.emote.setTexture(`emote-${view.emoteKind}-${emoteFrame(view.emoteKind, time)}`).setScale(motion.scale).setAlpha(motion.alpha)
      .setY(Math.max(EMOTE_Y - motion.lift, 16 - view.container.y));
  }

  /** One nearest-filtered texture per emote picture, drawn from its pixel map at twice its size. */
  private makeEmoteTextures(): void {
    for (const kind of EMOTE_KINDS) {
      emoteFrames(kind).forEach((rows: string[], frame: number): void => {
        const key: string = `emote-${kind}-${frame}`;
        this.textures.generate(key, { data: rows, pixelWidth: 2, palette: emotePalette(kind) as Phaser.Types.Create.Palette });
        this.textures.get(key).setFilter(Phaser.Textures.FilterMode.NEAREST);
      });
    }
  }

  private actorPose(actor: Actor): string {
    const wound: string | null = fightPose(actor);
    if (wound) return wound;
    if (actor.status === "walking") return "Walking";
    // Someone handing this visitor something holds it out to them; they reach for it, whatever they were doing.
    const offered: boolean = this.world?.actors.some((giver: Actor): boolean => giver.status === "interacting" && giver.action?.verb === "give" && giver.action.target_id === actor.id) ?? false;
    const pose: string | null | undefined = offered ? "Receiving" : actor.status === "interacting" && actor.action ? this.activities[actor.action.verb]?.pose : null;
    if (pose) return actor.seat_id ? SEATED_POSES[pose] ?? pose : pose;
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
    for (const view of this.visitors.values()) {
      if (view.emoteKind !== null && Math.hypot(pointer.x - view.container.x, pointer.y - view.container.y) <= this.world.map.tile_size * 0.65) {
        this.callbacks.hover(`${view.name.text} · ${EMOTE_WORDS[view.emoteKind]}`);
        return;
      }
    }
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
