/** The order menu: a floating list of the verbs open on a clicked thing; a row sends its action. */
import type { MenuRow } from "./orders";
import type { Action } from "./types";

export class OrderMenu {
  private readonly menu: HTMLElement = document.createElement("div");

  constructor(host: HTMLElement, private readonly handlers: { act: (action: Action) => void; inspect: () => void }) {
    this.menu.className = "order-menu";
    this.menu.hidden = true;
    host.append(this.menu);
    window.addEventListener("keydown", (event: KeyboardEvent): void => { if (event.key === "Escape") this.close(); });
    // A click anywhere else closes it; the capture phase runs before a click on the map opens the next one.
    window.addEventListener("pointerdown", (event: PointerEvent): void => { if (!this.menu.contains(event.target as Node)) this.close(); }, true);
  }

  /** Open at a page point with these rows; no rows shows "Nothing to do here now". */
  open(rows: readonly MenuRow[], at: { x: number; y: number }): void {
    this.menu.replaceChildren();
    if (rows.length === 0) {
      const empty: HTMLElement = document.createElement("span");
      empty.className = "order-empty";
      empty.textContent = "Nothing to do here now";
      this.menu.append(empty);
    }
    for (const row of rows) {
      const button: HTMLButtonElement = document.createElement("button");
      button.textContent = row.label;
      button.addEventListener("click", (): void => {
        this.close();
        if (row.action) this.handlers.act(row.action);
        else this.handlers.inspect();
      });
      this.menu.append(button);
    }
    this.menu.style.left = `${Math.min(at.x, window.innerWidth - 240)}px`;
    this.menu.style.top = `${Math.min(at.y, window.innerHeight - 40 - 30 * rows.length)}px`;
    this.menu.hidden = false;
  }

  close(): void {
    this.menu.hidden = true;
  }
}
