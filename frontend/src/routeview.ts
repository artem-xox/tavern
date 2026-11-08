/** The route, seat ribbons and obstacle spots drawn on the hall's route layer. */
import Phaser from "phaser";
import type { Actor, Cell, World, WorldObject } from "./types";

/** Redraw the selected visitor's route, every visitor's own-seat ribbon, and (when editing) the interaction spots. */
export function drawRoute(route: Phaser.GameObjects.Graphics, world: World | null, selectedId: string | null, editing: boolean): void {
  route.clear();
  if (!world) return;
  const size: number = world.map.tile_size;
  drawOwnSeats(route, world, size);
  const actor: Actor | undefined = world.actors.find((visitor: Actor): boolean => visitor.id === selectedId);
  if (actor && actor.path.length > 0) {
    const cells: Cell[] = [[actor.x, actor.y], ...actor.path];
    route.lineStyle(2, 0xf3d297, 0.8).beginPath();
    cells.forEach(([x, y]: Cell, index: number): void => {
      if (index === 0) route.moveTo((x + 0.5) * size, (y + 0.5) * size);
      else route.lineTo((x + 0.5) * size, (y + 0.5) * size);
    });
    route.strokePath();
    for (const [x, y] of actor.path) route.fillStyle(0xf3d297, 0.75).fillCircle((x + 0.5) * size, (y + 0.5) * size, 3);
  }
  if (editing) {
    for (const object of world.map.objects) {
      for (const [x, y] of object.interaction_spots) route.lineStyle(1, 0xe9d8a6, 0.4).strokeRect(x * size + 7, y * size + 7, size - 14, size - 14);
    }
  }
}

/** Mark each visitor's own seat with a ribbon in their colour, so a taken seat is visible. */
function drawOwnSeats(route: Phaser.GameObjects.Graphics, world: World, size: number): void {
  for (const actor of world.actors) {
    const seat: WorldObject | undefined = world.map.objects.find((object: WorldObject): boolean => object.id === actor.favorite_seat_id);
    if (!seat) continue;
    const color: number = Phaser.Display.Color.ValueToColor(actor.color).color;
    const x: number = (seat.x + (seat.facing === "west" ? 0.82 : 0.18)) * size;
    const y: number = (seat.y + 0.2) * size;
    route.fillStyle(0x221b16, 0.8).fillCircle(x, y, 4.5);
    route.fillStyle(color).fillCircle(x, y, 3.2);
  }
}
