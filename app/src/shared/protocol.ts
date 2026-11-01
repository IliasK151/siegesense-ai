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
