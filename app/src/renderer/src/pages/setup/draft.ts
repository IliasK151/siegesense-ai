import { type Profile, type ProfileField, profileFields } from "@shared/protocol";

export type ProfileDraft = Partial<Profile>;
export type WizardStep = "player" | "sensitivity" | "display";

export const WIZARD_STEPS = ["Welcome", "Player", "Sensitivity", "Display", "Done"] as const;

export const STEP_FIELDS: Record<WizardStep, ProfileField[]> = {
  player: ["in_game_name"],
  sensitivity: ["dpi", "yaw_sensitivity", "pitch_sensitivity", "ads_sensitivity"],
  display: ["fov", "resolution_width", "resolution_height", "hud_scale", "window_mode"],
};

const MESSAGES: Partial<Record<ProfileField, string>> = {
  in_game_name: "3–15 characters: letters, numbers, . _ -",
  dpi: "Between 100 and 32000",
  yaw_sensitivity: "Between 1 and 100",
  pitch_sensitivity: "Between 1 and 100",
  ads_sensitivity: "Each scope value must be between 1 and 200",
  fov: "Between 60 and 90",
  resolution_width: "Between 640 and 7680",
  resolution_height: "Between 480 and 4320",
  hud_scale: "Between 50 and 100",
};

/** Required fields that are still empty. They block Next but don't show an error yet. */
export function missingRequired(step: WizardStep, d: ProfileDraft): ProfileField[] {
  return STEP_FIELDS[step].filter((f) => d[f] === undefined && !profileFields[f].safeParse(undefined).success);
}

/** Field → message for values that are filled in but invalid. */
export function validateStep(step: WizardStep, d: ProfileDraft): Partial<Record<ProfileField, string>> {
  const errors: Partial<Record<ProfileField, string>> = {};
  for (const f of STEP_FIELDS[step]) {
    if (d[f] === undefined) continue;
    if (!profileFields[f].safeParse(d[f]).success) errors[f] = MESSAGES[f] ?? "Invalid value";
  }
  return errors;
}

export function stepIsValid(step: WizardStep, d: ProfileDraft): boolean {
  return missingRequired(step, d).length === 0 && Object.keys(validateStep(step, d)).length === 0;
}

/** Number input helper: empty string → undefined, otherwise a number. */
export function toNumber(raw: string): number | undefined {
  if (raw.trim() === "") return undefined;
  const n = Number(raw);
  return Number.isFinite(n) ? n : undefined;
}
