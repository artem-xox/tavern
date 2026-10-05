/** Static room surfaces, fittings and furniture rendered from the server map. */
import Phaser from "phaser";
import { drawDarts, drawDice, drawRugs, hearthFacing } from "./furniture";
import type { World, WorldObject } from "./types";

const TEXTURES: [string, string][] = [
  ["tavern-oak-floor", "/tavern/tiles/oak-floor.png"],
  ["tavern-slate-wall", "/tavern/tiles/slate-wall.png"],
  ["tavern-slate-window", "/tavern/tiles/slate-window.png"],
  ["tavern-slate-door", "/tavern/tiles/slate-door.png"],
  ["tavern-privy-stone", "/tavern/tiles/privy-stone.png"],
  ["tavern-privy-bucket", "/tavern/props/privy-bucket.png"],
  ["tavern-fireplace", "/tavern/props/fireplace.png"],
  ["tavern-bar", "/tavern/props/bar.png"],
  ["tavern-table", "/tavern/props/table.png"],
  ["tavern-chair", "/tavern/props/chair.png"],
  ["tavern-ale-cask", "/tavern/props/ale-cask.png"],
  ["tavern-barrel", "/tavern/decor/barrel.png"],
  ["tavern-plant", "/tavern/decor/plant.png"],
  ["tavern-candle", "/tavern/decor/candle.png"],
];

export class RoomArt {
  private floorArt!: Phaser.GameObjects.Image;
  private privyArt!: Phaser.GameObjects.Image;
  private floor!: Phaser.GameObjects.Graphics;
  private wallArt!: Phaser.GameObjects.Container;
  private glow!: Phaser.GameObjects.Graphics;
  private details!: Phaser.GameObjects.Graphics;
  private props: Phaser.GameObjects.Image[] = [];
  private mapSignature: string = "";
  private world: World | null = null;

  constructor(private readonly scene: Phaser.Scene) {}

  preload(): void {
    for (const [key, path] of TEXTURES) this.scene.load.image(key, path);
  }

  create(): void {
    for (const [key] of TEXTURES) this.scene.textures.get(key).setFilter(Phaser.Textures.FilterMode.NEAREST);
    this.floorArt = this.scene.add.image(0, 0, "tavern-oak-floor").setOrigin(0).setDepth(-2);
    this.privyArt = this.scene.add.image(0, 0, "tavern-privy-stone").setOrigin(0).setDepth(-1.5);
    this.floor = this.scene.add.graphics().setDepth(-1);
    this.wallArt = this.scene.add.container(0, 0).setDepth(0);
    this.glow = this.scene.add.graphics().setDepth(0.5);
    this.details = this.scene.add.graphics().setDepth(2);
  }

  render(world: World): void {
    const signature: string = JSON.stringify(world.map);
    this.world = world;
    if (signature === this.mapSignature) return;
    this.mapSignature = signature;
    const { width, height, tile_size: size } = world.map;
    this.scene.scale.resize(width * size, height * size);
    this.floorArt.setDisplaySize(width * size, height * size);
    const toilet: WorldObject | undefined = world.map.objects.find((object: WorldObject): boolean => object.kind === "toilet");
    this.privyArt.setVisible(Boolean(toilet));
    if (toilet) this.privyArt.setPosition((toilet.x - 1) * size, (toilet.y - 1) * size).setDisplaySize(3 * size, 3 * size);
    this.floor.clear();
    this.wallArt.removeAll(true);
    this.details.clear();
    for (const prop of this.props) prop.destroy();
    this.props = [];
    this.drawFloor(world);
    for (const object of world.map.objects) this.drawObject(object, size);
    this.drawDecor(world);
  }

  update(time: number): void {
    this.glow.clear();
    if (!this.world) return;
    const { width, tile_size: size } = this.world.map;
    const flicker: number = 0.82 + 0.1 * Math.sin(time / 170) + 0.08 * Math.sin(time / 53);
    for (const hearth of this.world.map.objects.filter((object: WorldObject): boolean => object.kind === "fireplace")) {
      const [dx, dy]: [number, number] = hearthFacing(hearth, width);
      const x: number = (hearth.x + (hearth.width ?? 1) / 2 + dx * 0.9) * size;
      const y: number = (hearth.y + (hearth.height ?? 1) / 2 + dy * 0.9) * size;
      for (let ring: number = 5; ring > 0; ring -= 1) {
        this.glow.fillStyle(0xf5a347, 0.045 * flicker).fillCircle(x, y, ring * size * 0.62 * flicker);
      }
    }
  }

  private drawFloor(world: World): void {
    const { tile_size: size, blocked } = world.map;
    this.floor.fillStyle(0xddd1aa, 0.35).fillRect(2.3 * size, 8.2 * size, 3, size * 0.6);
    drawRugs(this.floor, world.map.objects, size);
    for (const [x, y] of blocked) this.drawWall(x, y, size, "tavern-slate-wall");
    for (const object of world.map.objects.filter((item: WorldObject): boolean => ["window", "fireplace"].includes(item.kind))) {
      for (let dy: number = 0; dy < (object.height ?? 1); dy += 1) {
        for (let dx: number = 0; dx < (object.width ?? 1); dx += 1) {
          const texture: string = object.kind === "window" ? "tavern-slate-window" : "tavern-slate-wall";
          this.drawWall(object.x + dx, object.y + dy, size, texture);
        }
      }
    }
    for (const door of world.map.objects.filter((item: WorldObject): boolean => item.kind === "door")) {
      const image: Phaser.GameObjects.Image = this.scene.add.image(door.x * size, door.y * size, "tavern-slate-door")
        .setOrigin(0).setDisplaySize((door.width ?? 1) * size, (door.height ?? 1) * size);
      this.wallArt.add(image);
    }
  }

  private drawWall(x: number, y: number, size: number, texture: string): void {
    const image: Phaser.GameObjects.Image = this.scene.add.image((x + 0.5) * size, (y + 0.5) * size, texture).setDisplaySize(size, size);
    this.wallArt.add(image);
  }

  private addProp(texture: string, x: number, y: number, width: number, height: number, depth: number = 1): Phaser.GameObjects.Image {
    const image: Phaser.GameObjects.Image = this.scene.add.image(x, y, texture).setDisplaySize(width, height).setDepth(depth);
    this.props.push(image);
    return image;
  }

  private drawObject(object: WorldObject, size: number): void {
    const x: number = (object.x + 0.5) * size;
    const y: number = (object.y + 0.5) * size;
    if (object.kind === "fireplace") this.addProp("tavern-fireplace", (object.x + (object.width ?? 1) / 2) * size, y + 6, (object.width ?? 1) * size * 1.2, 64);
    if (object.kind === "bar") this.addProp("tavern-bar", (object.x + (object.width ?? 1) / 2) * size, y + 6, (object.width ?? 1) * size * 1.1, 82, 10 + (object.y + 0.9) * size / 1000);
    if (object.kind === "tap") this.addProp("tavern-ale-cask", x, y, 36, 36);
    if (object.kind === "toilet") this.addProp("tavern-privy-bucket", x, y, 30, 30);
    if (object.kind === "chair" || object.kind === "dice_chair") this.addProp("tavern-chair", x, y, 37, 37).setFlipX(object.facing === "west");
    if (object.kind === "table" || object.kind === "dice_table") this.addProp("tavern-table", x, y, 42, 42);
    if (object.kind === "dice_table") drawDice(this.details, object, size);
    if (object.kind === "darts") drawDarts(this.details, x, y);
    if (object.reserved_by) this.details.lineStyle(2, 0xe6c88d, 0.75).strokeCircle(x, y, 15);
  }

  private drawDecor(world: World): void {
    const { width, height, tile_size: size } = world.map;
    for (const [x, y] of [[width - 1.55, 7.6], [width - 1.55, height - 2.2]]) {
      this.addProp("tavern-barrel", x * size, y * size, 31, 31);
    }
    for (const [x, y] of [[1.55, 1.9], [width - 1.6, 4.7], [1.5, height - 1.7]]) {
      this.addProp("tavern-plant", x * size, y * size, 30, 30);
    }
    for (const table of world.map.objects.filter((object: WorldObject): boolean => object.kind === "table")) {
      this.addProp("tavern-candle", (table.x + 0.23) * size, (table.y + 0.24) * size, 16, 16, 3);
    }
  }
}
