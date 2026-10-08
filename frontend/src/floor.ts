/** Drawing of the hall's floor, rugs and walls, with the doors, windows and fireplace set into them. */
import Phaser from "phaser";
import { drawRugs } from "./furniture";
import type { World, WorldObject } from "./types";

/** Paint the whole floor, rugs and walls into `floor`, replacing what it held. */
export function drawFloor(floor: Phaser.GameObjects.Graphics, world: World): void {
  const { width, height, tile_size: size, blocked } = world.map;
  floor.clear();
  for (let y: number = 0; y < height; y += 1) {
    for (let x: number = 0; x < width; x += 1) {
      floor.fillStyle([0x896649, 0x936e4d, 0x8d694a][(x + y * 3) % 3]!);
      floor.fillRect(x * size, y * size, size, size);
      floor.lineStyle(1, 0x382f26, 0.23);
      floor.lineBetween(x * size, (y + 1) * size, (x + 1) * size, (y + 1) * size);
      floor.lineBetween((x + (y % 2 ? 0.5 : 0)) * size, y * size, (x + (y % 2 ? 0.5 : 0)) * size, (y + 1) * size);
      floor.lineStyle(1, 0xe2b887, 0.09);
      floor.lineBetween(x * size + 3, y * size + 10, (x + 1) * size - 3, y * size + 10);
    }
  }
  drawRoomDetails(floor, size);
  drawRugs(floor, world.map.objects, size);
  for (const [x, y] of blocked) drawWall(floor, x * size, y * size, size);
  // Doors, windows and the fireplace sit inside the outer wall.
  for (const object of world.map.objects.filter((item: WorldObject): boolean => ["door", "window", "fireplace"].includes(item.kind))) {
    for (let dy: number = 0; dy < (object.height ?? 1); dy += 1) {
      for (let dx: number = 0; dx < (object.width ?? 1); dx += 1) drawWall(floor, (object.x + dx) * size, (object.y + dy) * size, size);
    }
  }
}

function drawRoomDetails(floor: Phaser.GameObjects.Graphics, size: number): void {
  // The privy's floor: grey flagstones, each its own shade, laid with offset joints and a few chips.
  for (let x: number = 16; x < 19; x += 1) {
    for (let y: number = 1; y < 4; y += 1) {
      floor.fillStyle([0x9d937f, 0x958b77, 0xa39985][(x * 2 + y) % 3]!).fillRect(x * size, y * size, size, size);
      floor.lineStyle(1, 0x625a49, 0.65).strokeRect(x * size, y * size, size, size);
      floor.lineStyle(1, 0xb7ae9a, 0.4).lineBetween(x * size + 2, y * size + 2, (x + 1) * size - 3, y * size + 2);
      floor.fillStyle(0x625a49, 0.45).fillRect((x + 0.3 + 0.1 * ((x + y) % 3)) * size, (y + 0.65) * size, 3, 2);
    }
  }
  floor.fillStyle(0xddd1aa, 0.35).fillRect(2.3 * size, 8.2 * size, 3, size * 0.6);
  for (const [x, y] of [[2, 2], [10, 2]]) {
    for (let radius: number = 3; radius > 0; radius -= 1) {
      floor.fillStyle(0xf5ce82, 0.025).fillCircle((x! + 0.5) * size, (y! + 0.5) * size, radius * size);
    }
  }
}

function drawWall(floor: Phaser.GameObjects.Graphics, x: number, y: number, size: number): void {
  floor.fillStyle(0x332d29);
  floor.fillRect(x, y, size, size);
  floor.fillStyle(0x555048);
  floor.fillRoundedRect(x + 2, y + 2, size - 4, size - 5, 3);
  floor.lineStyle(2, 0x756b5b, 0.55);
  floor.lineBetween(x + 4, y + 3, x + size - 5, y + 3);
  floor.lineStyle(1, 0x292724, 0.5);
  floor.lineBetween(x + size / 2, y + 4, x + size / 2, y + size - 4);
}
