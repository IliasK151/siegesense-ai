import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { Profile, StatusPayload } from "@shared/protocol";
import type { ConnState } from "@/lib/engineClient";
import { EngineError } from "@/lib/engineClient";
import type { EngineLike } from "@/lib/engineContext";

const fixture = (name: string) =>
  JSON.parse(readFileSync(resolve(__dirname, "../../../protocol/fixtures", name), "utf8"));

export const statusFixture = (): StatusPayload => fixture("status.json").payload;
export const profileFixture = (): Profile => fixture("save_profile.json").payload.profile;

type Handler = (payload: Record<string, unknown>) => unknown;

/** In-memory stand-in for EngineClient. Handlers return data or throw EngineError. */
export class FakeEngine implements EngineLike {
  connState: ConnState = "open";
  calls: { type: string; payload: Record<string, unknown> }[] = [];
  handlers: Record<string, Handler> = {};
  private statusCbs = new Set<(s: StatusPayload) => void>();
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

  on(_type: "status", cb: (s: StatusPayload) => void) {
    this.statusCbs.add(cb);
    return () => this.statusCbs.delete(cb);
  }

  onState(cb: (s: ConnState) => void) {
    this.stateCbs.add(cb);
    return () => this.stateCbs.delete(cb);
  }

  emitStatus(s: StatusPayload) {
    for (const cb of this.statusCbs) cb(s);
  }

  emitState(s: ConnState) {
    this.connState = s;
    for (const cb of this.stateCbs) cb(s);
  }
}
