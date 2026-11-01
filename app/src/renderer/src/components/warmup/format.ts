export const pct = (rate: number) => `${Math.round(rate * 100)}%`;

export function fmtElapsed(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export type FlickTag = { label: "Clean" | "Correction" | "Overshoot"; tone: "ok" | "warn" | "error" };

export function flickTag(f: { overshoot: boolean; corrected: boolean }): FlickTag {
  if (f.overshoot) return { label: "Overshoot", tone: "error" };
  if (f.corrected) return { label: "Correction", tone: "warn" };
  return { label: "Clean", tone: "ok" };
}
