// Wire protocol between the app and the engine. Mirrors engine/src/siegesense_engine/protocol.py
// and profile.py. Both sides are tested against the samples in protocol/fixtures.
import { z } from "zod";

export const Envelope = z.object({
  type: z.string(),
  ts: z.number().int(),
  id: z.string().nullish(),
  payload: z.record(z.string(), z.unknown()).default({}),
});
export type Envelope = z.infer<typeof Envelope>;

export const LIGHT_KEYS = ["game", "capture", "input", "hud", "coach", "voice"] as const;
export const LightKey = z.enum(LIGHT_KEYS);
export type LightKey = z.infer<typeof LightKey>;

export const LightState = z.enum(["ok", "warn", "error", "off"]);
export type LightState = z.infer<typeof LightState>;

export const Light = z.object({
  state: LightState,
  label: z.string(),
  detail: z.string(),
  fix: z.string().nullish(),
});
export type Light = z.infer<typeof Light>;

export const StatusPayload = z.object({
  lights: z.record(LightKey, Light),
});
export type StatusPayload = z.infer<typeof StatusPayload>;

export const ErrorInfo = z.object({ code: z.string(), message: z.string() });
export type ErrorInfo = z.infer<typeof ErrorInfo>;

export const ResponsePayload = z.discriminatedUnion("ok", [
  z.object({ ok: z.literal(true), data: z.unknown() }),
  z.object({ ok: z.literal(false), error: ErrorInfo }),
]);
export type ResponsePayload = z.infer<typeof ResponsePayload>;

export const ADS_KEYS = ["1x", "2.5x", "3x", "4x", "5x", "12x"] as const;
export type AdsKey = (typeof ADS_KEYS)[number];
export const NAME_PATTERN = /^[A-Za-z0-9._-]{3,15}$/;
export const WindowMode = z.enum(["fullscreen", "windowed", "borderless", "unknown"]);
export type WindowMode = z.infer<typeof WindowMode>;

const int = (min: number, max: number) => z.number().int().min(min).max(max);

// --- HUD regions (engine/src/siegesense_engine/hud/regions.py) -----------------------------
export const Box = z
  .object({ x: z.number().min(0).max(1), y: z.number().min(0).max(1), w: z.number().gt(0).max(1), h: z.number().gt(0).max(1) })
  .refine((b) => b.x + b.w <= 1.0001 && b.y + b.h <= 1.0001, "box must fit inside the screen");
export type Box = z.infer<typeof Box>;

export const HUD_REGION_KEYS = ["killfeed", "timer", "score_left", "score_right", "health", "centre"] as const;
export type HudRegionKey = (typeof HUD_REGION_KEYS)[number];
export const DEFAULT_HUD_REGIONS: Record<HudRegionKey, Box> = {
  killfeed: { x: 0.7, y: 0.08, w: 0.29, h: 0.22 },
  timer: { x: 0.47, y: 0.015, w: 0.06, h: 0.045 },
  score_left: { x: 0.42, y: 0.015, w: 0.04, h: 0.045 },
  score_right: { x: 0.54, y: 0.015, w: 0.04, h: 0.045 },
  health: { x: 0.02, y: 0.88, w: 0.07, h: 0.07 },
  centre: { x: 0.4, y: 0.4, w: 0.2, h: 0.2 },
};
export const HudRegions = z.object({
  killfeed: Box,
  timer: Box,
  score_left: Box,
  score_right: Box,
  health: Box,
  centre: Box,
});
export type HudRegions = z.infer<typeof HudRegions>;

/** Field schemas, exported individually so forms can validate one step at a time. */
export const profileFields = {
  in_game_name: z.string().regex(NAME_PATTERN, "3–15 characters: letters, numbers, . _ -"),
  dpi: int(100, 32000),
  yaw_sensitivity: int(1, 100),
  pitch_sensitivity: int(1, 100),
  mouse_multiplier_unit: z.number().gt(0).max(1).default(0.02),
  x_factor_aiming: z.number().gt(0).max(1).default(0.02),
  ads_sensitivity: z.partialRecord(z.enum(ADS_KEYS), int(1, 200)).default({}),
  fov: z.number().min(60).max(90).default(75),
  resolution_width: int(640, 7680).default(1920),
  resolution_height: int(480, 4320).default(1080),
  hud_scale: int(50, 100).default(100),
  window_mode: WindowMode.default("unknown"),
  counts_per_360: z.number().gt(0).nullish(),
  hud_regions: HudRegions.default(DEFAULT_HUD_REGIONS),
  my_score_side: z.enum(["left", "right"]).default("left"),
  capture_fps: int(20, 60).default(30),
};

export const Profile = z.object(profileFields);
export type Profile = z.infer<typeof Profile>;
export type ProfileField = keyof typeof profileFields;

export const GameSettingsFile = z.object({ path: z.string(), modified: z.number() });
export type GameSettingsFile = z.infer<typeof GameSettingsFile>;

export const GameSettingsImport = z.object({
  values: Profile.partial(),
  missing: z.array(z.string()),
  source: z.string(),
});
export type GameSettingsImport = z.infer<typeof GameSettingsImport>;

// --- Warm-up Mode (engine/src/siegesense_engine/warmup.py) ---------------------------------
export const Conversion = z.enum(["calibrated", "estimated"]);
export type Conversion = z.infer<typeof Conversion>;

export const WarmupMetrics = z.object({
  elapsed_s: z.number(),
  flicks: z.number().int(),
  corrected: z.number().int(),
  overshoots: z.number().int(),
  overshoot_rate: z.number(),
  correction_rate: z.number(),
  avg_amplitude: z.number(),
  avg_peak_speed: z.number(),
  shots: z.number().int(),
  taps: z.number().int(),
  bursts: z.number().int(),
  sprays: z.number().int(),
  moving_shots: z.number().int(),
  moving_shot_rate: z.number(),
  strafe_switches: z.number().int(),
  crouch_spams: z.number().int(),
  ads_jitter_per_s: z.number(),
  reaction_ms: z.number().nullable().default(null),
  reactions: z.number().int().default(0),
  score: z.number().int().nullable(),
  conversion: Conversion,
});
export type WarmupMetrics = z.infer<typeof WarmupMetrics>;

export const Flick = z.object({
  id: z.number().int(),
  t_peak: z.number(),
  amplitude: z.number(),
  peak_speed: z.number(),
  duration_ms: z.number(),
  direction: z.number(),
  reversal: z.number(),
  corrected: z.boolean(),
  overshoot: z.boolean(),
  shot: z.boolean(),
  trace: z.array(z.tuple([z.number(), z.number()])),
});
export type Flick = z.infer<typeof Flick>;

export const Drill = z.object({ key: z.string(), title: z.string(), text: z.string() });
export type Drill = z.infer<typeof Drill>;

export const HistoryPoint = z.object({ started_at: z.string(), score: z.number().int().nullable() });
export type HistoryPoint = z.infer<typeof HistoryPoint>;

export const WarmupSummary = z.object({
  id: z.number().int().nullable(),
  started_at: z.string(),
  duration_s: z.number(),
  metrics: WarmupMetrics,
  drill: Drill.nullable(),
  message: z.string(),
  history: z.array(HistoryPoint),
});
export type WarmupSummary = z.infer<typeof WarmupSummary>;

// --- 360° calibration (engine/src/siegesense_engine/calibration.py) -------------------------
export const CalibrationState = z.object({
  phase: z.enum(["armed", "measuring", "done", "cancelled"]),
  runs: z.array(z.number().int()),
  current_counts: z.number().int(),
  target_runs: z.number().int(),
  result: z.number().nullable(),
  spread: z.number().nullable(),
  warning: z.string().nullable(),
});
export type CalibrationState = z.infer<typeof CalibrationState>;

// --- Live Mode (engine/src/siegesense_engine/rounds.py, live.py, hud/reader.py) --------------
export const LiveEvent = z.object({
  kind: z.enum(["round_start", "phase", "kill", "death", "round_end", "repeek"]),
  t: z.number(),
  round: z.number().int(),
  data: z.record(z.string(), z.unknown()).default({}),
  confidence: z.enum(["ok", "low"]),
  clip: z.string().nullable().default(null),
});
export type LiveEvent = z.infer<typeof LiveEvent>;

export const RoundSummary = z.object({
  number: z.number().int(),
  phase_seen: z.array(z.enum(["prep", "action"])),
  started_t: z.number(),
  ended_t: z.number().nullable(),
  result: z.enum(["win", "loss"]).nullable(),
  kills: z.number().int(),
  died: z.boolean(),
  death_confidence: z.enum(["ok", "low"]).nullable(),
  time_alive_s: z.number().nullable(),
  first_blood: z.boolean(),
  first_death: z.boolean(),
  traded: z.boolean(),
  traded_teammate: z.number().int(),
  repeeks: z.number().int(),
});
export type RoundSummary = z.infer<typeof RoundSummary>;

export const DeathInfo = z.object({
  round: z.number().int(),
  killer: z.string().nullable(),
  time_alive_s: z.number().nullable(),
  confidence: z.enum(["ok", "low"]),
  clip: z.string().nullable(),
});
export type DeathInfo = z.infer<typeof DeathInfo>;

export const MatchSummary = z.object({
  id: z.number().int().nullable(),
  started_at: z.string(),
  ended_at: z.string(),
  rounds: z.array(RoundSummary),
  deaths: z.array(DeathInfo),
});
export type MatchSummary = z.infer<typeof MatchSummary>;

export const ReaderResult = z.object({
  key: z.string(),
  text: z.string(),
  confidence: z.number(),
  ok: z.boolean(),
});
export type ReaderResult = z.infer<typeof ReaderResult>;

export const HudCheckResult = z.object({
  image_jpeg_b64: z.string(),
  width: z.number().int(),
  height: z.number().int(),
  regions: HudRegions,
  readers: z.array(ReaderResult),
});
export type HudCheckResult = z.infer<typeof HudCheckResult>;
