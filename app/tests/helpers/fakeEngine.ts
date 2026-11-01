import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { Profile, StatusPayload } from "@shared/protocol";
import type { ConnState, PushMap, PushType } from "@/lib/engineClient";
import { EngineError } from "@/lib/engineClient";
import type { EngineLike } from "@/lib/engineContext";

const fixture = (name: string) =>
  JSON.parse(readFileSync(resolve(__dirname, "../../../protocol/fixtures", name), "utf8"));

export const statusFixture = (): StatusPayload => fixture("status.json").payload;
export const profileFixture = (): Profile => fixture("save_profile.json").payload.profile;
export const metricsFixture = () => fixture("metrics.json").payload;
export const flickFixture = () => fixture("flick.json").payload;
export const calibrationFixture = () => fixture("calibration.json").payload;
export const summaryFixture = () => fixture("warmup_summary.json").payload.data;

type Handler = (payload: Record<string, unknown>) => unknown;

/** In-memory stand-in for EngineClient. Handlers return data or throw EngineError. */
export class FakeEngine implements EngineLike {
  connState: ConnState = "open";
  calls: { type: string; payload: Record<string, unknown> }[] = [];
  handlers: Record<string, Handler> = {};
  private pushCbs: { [K in PushType]: Set<(p: PushMap[K]) => void> } = {
    status: new Set(),
    metrics: new Set(),
    flick: new Set(),
    calibration: new Set(),
  };
  private stateCbs = new Set<(s: ConnState) => void>();

  constructor(opts: { profile?: Profile | null; status?: StatusPayload } = {}) {
    let profile = opts.profile === undefined ? profileFixture() : opts.profile;
    this.handlers = {
      get_profile: () => ({ profile }),
      save_profile: (p) => {
        profile = p.profile as Profile;
        return { profile };
      },
      get_status: () => opts.status ?? statusFixture(),
      find_game_settings: () => ({ files: [] }),
    };
  }

  async connect() {}
  close() {}

  async request<T>(type: string, payload: object = {}): Promise<T> {
    this.calls.push({ type, payload: payload as Record<string, unknown> });
    const h = this.handlers[type];
    if (!h) throw new EngineError("unknown_type", type);
    return (await h(payload as Record<string, unknown>)) as T;
  }

  on<K extends PushType>(type: K, cb: (p: PushMap[K]) => void) {
    this.pushCbs[type].add(cb);
    return () => {
      this.pushCbs[type].delete(cb);
    };
  }

  emit<K extends PushType>(type: K, payload: PushMap[K]) {
    for (const cb of this.pushCbs[type]) cb(payload);
  }

  onState(cb: (s: ConnState) => void) {
    this.stateCbs.add(cb);
    return () => this.stateCbs.delete(cb);
  }

  emitStatus(s: StatusPayload) {
    this.emit("status", s);
  }

  emitState(s: ConnState) {
    this.connState = s;
    for (const cb of this.stateCbs) cb(s);
  }
}
