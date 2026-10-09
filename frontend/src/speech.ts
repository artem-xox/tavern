/** A guest's speech bubble: built once, told line by line in pieces, and drawn whole inside the map. */
import Phaser from "phaser";
import { chunkAt, placeBubble, splitLine, type Spoken } from "./bubble";

/** Speech bubbles wrap at this many pixels and draw above every guest. */
const BUBBLE_WRAP = 150;
const BUBBLE_FILL = 0xf4e6c6;
const BUBBLE_EDGE = 0x6b5640;
/** Length and half-width of a bubble's pointer, and how far from a corner its tip stays. */
const TAIL = 7;
const TAIL_HALF = 6;
const TAIL_INSET = 14;
const BUBBLE_DEPTH = 1000;

export class Speech {
  private readonly box: Phaser.GameObjects.Graphics;
  private readonly text: Phaser.GameObjects.Text;
  private readonly container: Phaser.GameObjects.Container;
  /** The line being told in pieces, and when it began. */
  private talk: { key: string; chunks: string[]; start: number } | null = null;

  constructor(scene: Phaser.Scene) {
    // Outside the guest's container, so it can sit above every guest and be kept inside the map each frame.
    this.box = scene.add.graphics();
    this.text = scene.add.text(0, 0, "", { fontFamily: "Georgia", fontSize: "11px", color: "#48392b", align: "center", lineSpacing: 2, padding: { x: 9, y: 6 }, wordWrap: { width: BUBBLE_WRAP, useAdvancedWrap: true } }).setOrigin(0.5, 0);
    this.container = scene.add.container(0, 0, [this.box, this.text]).setDepth(BUBBLE_DEPTH).setVisible(false);
  }

  /**
   * Tell the latest line its speaker has to say over them in pieces; the server keeps a scene up while the last one is heard.
   *
   * @param line The speaker's latest line, from their conversation or a call of their own, or null when they have none.
   * @param now Real time in milliseconds, for the piece's start.
   */
  tell(line: Spoken | null, now: number): void {
    if (line === null) { this.talk = null; return; }
    const key: string = `${line.time}:${line.line}`;
    if (this.talk?.key !== key) this.talk = { key, chunks: splitLine(line.line), start: now };
  }

  /**
   * Show the piece of the line now due over its speaker, inside the map and above the other guests.
   *
   * @param speakerX Speaker's x in map pixels.
   * @param speakerY Speaker's y in map pixels.
   * @param now Real time in milliseconds.
   * @param map Map size in pixels.
   */
  place(speakerX: number, speakerY: number, now: number, map: { width: number; height: number }): void {
    this.container.setVisible(this.talk !== null);
    if (!this.talk) return;
    const piece: string = this.talk.chunks[chunkAt(this.talk.chunks, now - this.talk.start)]!;
    if (this.text.text !== piece) this.text.setText(piece);
    const { width, height } = this.text;
    const placement = placeBubble(speakerX, speakerY, width, height, map);
    this.container.setPosition(placement.x, placement.y);
    this.draw(width, height, placement.originY, speakerX - placement.x);
  }

  destroy(): void {
    this.container.destroy();
  }

  /** Draw the bubble's body around its text, with a pointer toward the speaker at `speakerDx` from its centre. */
  private draw(width: number, height: number, originY: 0 | 1, speakerDx: number): void {
    const top: number = originY === 1 ? -height : 0;
    const down: number = originY === 1 ? 1 : -1;
    const tailX: number = Math.min(Math.max(speakerDx, -width / 2 + TAIL_INSET), width / 2 - TAIL_INSET);
    const baseY: number = originY === 1 ? top + height : top;
    const box: Phaser.GameObjects.Graphics = this.box.clear();
    box.fillStyle(BUBBLE_FILL).fillRoundedRect(-width / 2, top, width, height, 9);
    box.lineStyle(2, BUBBLE_EDGE).strokeRoundedRect(-width / 2, top, width, height, 9);
    box.fillStyle(BUBBLE_FILL).fillRect(tailX - TAIL_HALF + 1, baseY - 1, 2 * TAIL_HALF - 2, 2);
    box.fillTriangle(tailX - TAIL_HALF, baseY, tailX + TAIL_HALF, baseY, tailX, baseY + down * TAIL);
    box.lineBetween(tailX - TAIL_HALF, baseY, tailX, baseY + down * TAIL);
    box.lineBetween(tailX + TAIL_HALF, baseY, tailX, baseY + down * TAIL);
    this.text.setY(top);
  }
}
