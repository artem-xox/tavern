import type { Command, Snapshot } from "./types";

interface Callbacks {
  snapshot: (snapshot: Snapshot) => void;
  status: (connected: boolean, message: string) => void;
  error: (message: string) => void;
}

/** Connect the view to the authoritative world and reconnect after interruptions. */
export class WorldConnection {
  private socket: WebSocket | null = null;
  private retryDelay: number = 500;
  private retryTimer: ReturnType<typeof setTimeout> | undefined;
  private disposed: boolean = false;

  constructor(private readonly callbacks: Callbacks) {
    this.connect();
  }

  /** Send a game command; disconnected commands are never queued or replayed. */
  send(command: Command): void {
    if (this.socket?.readyState !== WebSocket.OPEN) {
      this.callbacks.error("Disconnected. Wait for the server to reconnect.");
      return;
    }
    this.socket.send(JSON.stringify(command));
  }

  /** Release the connection when the browser page is closed. */
  dispose(): void {
    this.disposed = true;
    clearTimeout(this.retryTimer);
    this.socket?.close();
  }

  private connect(): void {
    this.callbacks.status(false, "Connecting to the tavern…");
    const protocol: string = location.protocol === "https:" ? "wss:" : "ws:";
    this.socket = new WebSocket(`${protocol}//${location.host}/ws`);
    this.socket.onopen = (): void => {
      this.retryDelay = 500;
      this.callbacks.status(true, "Live · server connected");
    };
    this.socket.onmessage = (event: MessageEvent<string>): void => this.receive(event.data);
    this.socket.onclose = (): void => this.reconnect();
    this.socket.onerror = (): void => this.socket?.close();
  }

  private receive(data: string): void {
    try {
      const message: Snapshot | { type: "error"; message: string } = JSON.parse(data);
      if (message.type === "snapshot") this.callbacks.snapshot(message);
      if (message.type === "error") this.callbacks.error(message.message);
    } catch (error: unknown) {
      this.callbacks.error(`Could not display server state: ${String(error)}`);
    }
  }

  private reconnect(): void {
    if (this.disposed) return;
    this.callbacks.status(false, "Disconnected · reconnecting…");
    this.retryTimer = setTimeout((): void => this.connect(), this.retryDelay);
    this.retryDelay = Math.min(this.retryDelay * 2, 8000);
  }
}
