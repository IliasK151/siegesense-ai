import { Crosshair, RotateCcw } from "lucide-react";
import { useState } from "react";
import { CalibrationPanel } from "@/components/calibration/CalibrationPanel";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { cmPer360, fmtInt } from "@/lib/aim";
import { EngineError } from "@/lib/engineClient";
import { useEngine, useProfile } from "@/lib/engineContext";
import { useNav } from "@/store/nav";
import { PageHeader } from "./PageHeader";
import { ProfileSummary } from "./ProfileSummary";

export function Settings() {
  const engine = useEngine();
  const { profile, reload } = useProfile();
  const go = useNav((s) => s.go);
  const [calibrating, setCalibrating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function saveCalibration(counts: number) {
    if (!profile) return;
    setError(null);
    try {
      await engine.request("save_profile", { profile: { ...profile, counts_per_360: counts } });
      await reload();
      setCalibrating(false);
    } catch (err) {
      setError(err instanceof EngineError ? err.message : "Could not save the calibration.");
    }
  }

  return (
    <>
      <PageHeader title="Settings" subtitle="Your profile and app preferences." />
      <div className="flex flex-col gap-5">
        <Card
          title={profile ? `Profile · ${profile.in_game_name}` : "Profile"}
          action={
            <Button size="sm" icon={RotateCcw} onClick={() => go("setup")}>
              Re-run setup
            </Button>
          }
        >
          {profile && <ProfileSummary profile={profile} />}
        </Card>

        <Card
          title="360° calibration"
          action={
            !calibrating && (
              <Button size="sm" icon={Crosshair} onClick={() => setCalibrating(true)}>
                Calibrate
              </Button>
            )
          }
        >
          {profile?.counts_per_360 ? (
            <p className="flex items-center gap-2 text-sm">
              <Badge tone="ok">Calibrated</Badge>
              <span className="font-mono">{fmtInt(profile.counts_per_360)} counts</span>
              <span className="text-muted">· {cmPer360(profile).toFixed(1)} cm/360</span>
            </p>
          ) : (
            <p className="flex items-center gap-2 text-sm">
              <Badge tone="warn">Estimated</Badge>
              <span className="text-muted">Not calibrated — using estimate from your sensitivity.</span>
            </p>
          )}
          {calibrating && (
            <div className="mt-4">
              <CalibrationPanel dpi={profile?.dpi} onResult={saveCalibration} onCancel={() => setCalibrating(false)} />
            </div>
          )}
          {error && (
            <p role="alert" className="mt-3 text-xs text-error">
              {error}
            </p>
          )}
        </Card>
      </div>
    </>
  );
}
