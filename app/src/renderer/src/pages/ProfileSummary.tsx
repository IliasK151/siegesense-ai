import type { Profile } from "@shared/protocol";
import { cmPer360 } from "@/lib/aim";

const modeLabel = { fullscreen: "Fullscreen", windowed: "Windowed", borderless: "Borderless", unknown: "Unknown" };

function Stat({ label, value, testId }: { label: string; value: string | number; testId?: string }) {
  return (
    <div className="rounded-xl bg-surface-2 px-3.5 py-3">
      <p className="text-[11px] uppercase tracking-[0.12em] text-muted">{label}</p>
      <p data-testid={testId} className="mt-1 truncate font-mono text-lg font-semibold">
        {value}
      </p>
    </div>
  );
}

export function edpi(p: Pick<Profile, "dpi" | "yaw_sensitivity">): number {
  return p.dpi * p.yaw_sensitivity;
}

export function ProfileSummary({ profile }: { profile: Profile }) {
  const calibrated = Boolean(profile.counts_per_360);
  return (
    <div className="grid grid-cols-4 gap-2.5">
      <Stat label="DPI" value={profile.dpi} />
      <Stat label="Sensitivity" value={`${profile.yaw_sensitivity} / ${profile.pitch_sensitivity}`} />
      <Stat label="eDPI" value={edpi(profile)} testId="edpi" />
      <Stat label={calibrated ? "cm/360" : "cm/360 (est.)"} value={cmPer360(profile).toFixed(1)} />
      <Stat label="FOV" value={profile.fov} />
      <Stat label="Resolution" value={`${profile.resolution_width}×${profile.resolution_height}`} />
      <Stat label="Display" value={modeLabel[profile.window_mode]} />
      <Stat label="Aim" value={calibrated ? "Calibrated" : "Estimated"} />
    </div>
  );
}
