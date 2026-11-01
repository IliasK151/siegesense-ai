// WebSocket client for the local engine: authenticates, sends requests, delivers pushes,
// and reconnects with backoff when the connection drops.
import { Envelope, ResponsePayload, StatusPayload } from "@shared/protocol";

export type EngineConnection = { port: number; token: string };
export type ConnState = "connecting" | "open" | "reconnecting" | "closed";

export class EngineError extends Error {
  constructor(
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "EngineError";
  }
}

type Pending = { resolve: (v: unknown) => void; reject: (e: EngineError) => void; timer: ReturnType<typeof setTimeout> };
type Options = { WebSocketImpl?: typeof WebSocket; backoffMs?: number[]; requestTimeoutMs?: number };
type PushMap = { status: StatusPayload };

export class EngineClient {
  private ws: WebSocket | null = null;
  private state: ConnState = "closed";
  private nextId = 1;
  private attempt = 0;
  private closedByUser = false;
  private pending = new Map<string, Pending>();
  private pushListeners: { [K in keyof PushMap]: Set<(p: PushMap[K]) => void> } = { status: new Set() };
  private stateListeners = new Set<(s: ConnState) => void>();
  private connectPromise: Promise<void> | null = null;
  private readonly WS: typeof WebSocket;
  private readonly backoff: number[];
  private readonly timeoutMs: number;

  constructor(
    private readonly getConn: () => Promise<EngineConnection>,
    opts: Options = {},
  ) {
    this.WS = opts.WebSocketImpl ?? WebSocket;
    this.backoff = opts.backoffMs ?? [250, 500, 1000, 2000, 4000];
    this.timeoutMs = opts.requestTimeoutMs ?? 8000;
  }

  get connState(): ConnState {
    return this.state;
  }

  connect(): Promise<void> {
    this.closedByUser = false;
    this.connectPromise ??= this.open("connecting");
    return this.connectPromise;
  }

  request<T = unknown>(type: string, payload: object = {}): Promise<T> {
    const ws = this.ws;
    if (!ws || this.state !== "open") {
      return Promise.reject(new EngineError("disconnected", "Not connected to the engine."));
    }
    return this.send<T>(ws, type, payload);
  }

  on<K extends keyof PushMap>(type: K, cb: (p: PushMap[K]) => void): () => void {
    this.pushListeners[type].add(cb);
    return () => this.pushListeners[type].delete(cb);
  }

  onState(cb: (s: ConnState) => void): () => void {
    this.stateListeners.add(cb);
    return () => this.stateListeners.delete(cb);
  }

  close(): void {
    this.closedByUser = true;
    this.ws?.close();
    this.ws = null;
    this.failPending();
    this.setState("closed");
  }

  // -- internals ----------------------------------------------------------------------------
  private setState(s: ConnState): void {
    if (this.state === s) return;
    this.state = s;
    for (const cb of this.stateListeners) cb(s);
  }

  private send<T>(ws: WebSocket, type: string, payload: object): Promise<T> {
    const id = String(this.nextId++);
    return new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new EngineError("timeout", `The engine did not answer "${type}" in time.`));
      }, this.timeoutMs);
      this.pending.set(id, { resolve: resolve as (v: unknown) => void, reject, timer });
      ws.send(JSON.stringify({ type, id, ts: Math.round(performance.now()), payload }));
    });
  }

  private failPending(): void {
    for (const [id, p] of this.pending) {
      clearTimeout(p.timer);
      p.reject(new EngineError("disconnected", "Lost connection to the engine."));
      this.pending.delete(id);
    }
  }

  private async open(phase: "connecting" | "reconnecting"): Promise<void> {
    this.setState(phase);
    while (!this.closedByUser) {
      try {
        await this.openOnce();
        this.attempt = 0;
        this.setState("open");
        return;
      } catch {
        const delay = this.backoff[Math.min(this.attempt, this.backoff.length - 1)] ?? 1000;
        this.attempt += 1;
        await new Promise((r) => setTimeout(r, delay));
      }
    }
  }

  private async openOnce(): Promise<void> {
    const { port, token } = await this.getConn();
    const ws = new this.WS(`ws://127.0.0.1:${port}`);
    await new Promise<void>((resolve, reject) => {
      ws.onopen = () => resolve();
      ws.onerror = () => reject(new Error("socket error"));
      ws.onclose = () => reject(new Error("socket closed"));
    });
    ws.onmessage = (ev) => this.onMessage(String(ev.data));
    ws.onclose = () => this.onClose(ws);
    ws.onerror = () => {};
    this.ws = ws;
    try {
      await this.send(ws, "hello", { token });
    } catch (err) {
      ws.close();
      throw err;
    }
  }

  private onMessage(raw: string): void {
    let env: Envelope;
    try {
      env = Envelope.parse(JSON.parse(raw));
    } catch {
      return;
    }
    if (env.type === "response") {
      const pending = env.id ? this.pending.get(env.id) : undefined;
      if (!pending || !env.id) return;
      this.pending.delete(env.id);
      clearTimeout(pending.timer);
      const res = ResponsePayload.safeParse(env.payload);
      if (!res.success) pending.reject(new EngineError("bad_response", "Malformed engine response."));
      else if (res.data.ok) pending.resolve(res.data.data);
      else pending.reject(new EngineError(res.data.error.code, res.data.error.message));
      return;
    }
    if (env.type === "status") {
      const status = StatusPayload.safeParse(env.payload);
      if (status.success) for (const cb of this.pushListeners.status) cb(status.data);
    }
  }

  private onClose(ws: WebSocket): void {
    if (ws !== this.ws) return;
    this.ws = null;
    this.failPending();
    if (this.closedByUser) return;
    this.connectPromise = this.open("reconnecting");
  }
}
