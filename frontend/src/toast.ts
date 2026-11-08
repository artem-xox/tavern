/** A short message that floats above a figure and goes away after a few seconds. */
import Phaser from "phaser";

const TOAST_MS = 3000;
const TOAST_Y = -90;

/** Add the message to the figure's container, so it follows them; it removes itself after 3 s. */
export function floatToast(scene: Phaser.Scene, figure: Phaser.GameObjects.Container, message: string): void {
  const text: Phaser.GameObjects.Text = scene.add.text(0, TOAST_Y, message, {
    fontFamily: "sans-serif", fontSize: "11px", color: "#fff3d6", backgroundColor: "#7a2e22", padding: { x: 5, y: 3 }, wordWrap: { width: 150 }, align: "center",
  }).setOrigin(0.5, 1);
  figure.add(text);
  scene.time.delayedCall(TOAST_MS, (): void => text.destroy());
}
