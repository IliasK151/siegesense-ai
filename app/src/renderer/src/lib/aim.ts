import type { Profile } from "@shared/protocol";

// Mirrors engine/src/siegesense_engine/mechanics/sensitivity.py
const RAD_TO_DEG_MILLI = 0.0572957795;

type AimInputs = Pick<Profile, "yaw_sensitivity" | "mouse_multiplier_unit" | "dpi"> & {
  counts_per_360?: number | null;
};

export function estimatedCountsPer360(p: Pick<Profile, "yaw_sensitivity" | "mouse_multiplier_unit">): number {
  return 360 / (p.yaw_sensitivity * p.mouse_multiplier_unit * RAD_TO_DEG_MILLI);
}

export function countsPer360(p: AimInputs): number {
  return p.counts_per_360 || estimatedCountsPer360(p);
}

export function cmPer360(p: AimInputs): number {
  return (countsPer360(p) / p.dpi) * 2.54;
}

export const fmtInt = (n: number) => Math.round(n).toLocaleString("en-US");
