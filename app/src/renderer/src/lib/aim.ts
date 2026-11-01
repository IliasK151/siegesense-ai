import type { Profile } from "@shared/protocol";

// Mirrors engine/src/siegesense_engine/mechanics/sensitivity.py
const YAW_PER_SENS_POINT = 0.00572957795; // degrees per count per sensitivity point at multiplier 0.02
const DEFAULT_MULTIPLIER = 0.02;

type AimInputs = Pick<Profile, "yaw_sensitivity" | "mouse_multiplier_unit" | "dpi"> & {
  counts_per_360?: number | null;
};

export function estimatedCountsPer360(p: Pick<Profile, "yaw_sensitivity" | "mouse_multiplier_unit">): number {
  return 360 / (p.yaw_sensitivity * (p.mouse_multiplier_unit / DEFAULT_MULTIPLIER) * YAW_PER_SENS_POINT);
}

export function countsPer360(p: AimInputs): number {
  return p.counts_per_360 || estimatedCountsPer360(p);
}

export function cmPer360(p: AimInputs): number {
  return (countsPer360(p) / p.dpi) * 2.54;
}

export const fmtInt = (n: number) => Math.round(n).toLocaleString("en-US");
