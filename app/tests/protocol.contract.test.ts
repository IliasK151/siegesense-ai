import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  CalibrationState,
  Envelope,
  HudCheckResult,
  LiveEvent,
  MatchSummary,
  RoundSummary,
  Flick,
  Profile,
  ResponsePayload,
  StatusPayload,
  WarmupMetrics,
  WarmupSummary,
} from "@shared/protocol";

const dir = resolve(__dirname, "../../protocol/fixtures");
const load = (name: string) => JSON.parse(readFileSync(resolve(dir, name), "utf8"));

describe("protocol contract", () => {
  it("parses every fixture as an envelope", () => {
    const files = readdirSync(dir).filter((f) => f.endsWith(".json"));
    expect(files.length).toBeGreaterThanOrEqual(5);
    for (const f of files) expect(() => Envelope.parse(load(f))).not.toThrow();
  });

  it("status fixture matches StatusPayload", () => {
    const status = StatusPayload.parse(load("status.json").payload);
    expect(Object.keys(status.lights)).toHaveLength(6);
  });

  it("save_profile fixture holds a valid Profile", () => {
    const profile = Profile.parse(load("save_profile.json").payload.profile);
    expect(profile.in_game_name).toBe("Ash.Main");
  });

  it("rejects invalid profile values", () => {
    const valid = load("save_profile.json").payload.profile;
    for (const bad of [{ dpi: 0 }, { in_game_name: "ab" }, { fov: 120 }, { ads_sensitivity: { "7x": 5 } }]) {
      expect(Profile.safeParse({ ...valid, ...bad }).success).toBe(false);
    }
  });

  it("response fixtures match ResponsePayload", () => {
    expect(ResponsePayload.parse(load("response_ok.json").payload).ok).toBe(true);
    expect(ResponsePayload.parse(load("response_error.json").payload).ok).toBe(false);
  });

  it("warm-up and calibration fixtures match their schemas", () => {
    expect(WarmupMetrics.parse(load("metrics.json").payload).flicks).toBe(12);
    expect(Flick.parse(load("flick.json").payload).id).toBe(1);
    expect(CalibrationState.parse(load("calibration.json").payload).phase).toBe("measuring");
    const summary = WarmupSummary.parse(load("warmup_summary.json").payload.data);
    expect(summary.drill?.key).toBe("overshoot");
    expect(summary.history.at(-1)?.score).toBe(summary.metrics.score);
  });

  it("live mode fixtures match their schemas", () => {
    expect(LiveEvent.parse(load("live_event.json").payload).clip).toMatch(/\.mp4$/);
    expect(RoundSummary.parse(load("round_summary.json").payload).died).toBe(true);
    expect(HudCheckResult.parse(load("hud_check.json").payload.data).readers).toHaveLength(5);
    expect(MatchSummary.parse(load("match_summary.json").payload.data).deaths).toHaveLength(1);
  });
});

