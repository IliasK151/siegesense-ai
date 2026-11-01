import { CircleCheck } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { CalibrationPanel } from "@/components/calibration/CalibrationPanel";
import { fmtInt } from "@/lib/aim";
import type { ProfileDraft } from "./draft";

type Props = { draft: ProfileDraft; update: (d: ProfileDraft) => void; onContinue: () => void };

export function StepCalibrate({ draft, update, onContinue }: Props) {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Calibrate your aim</h1>
      <p className="mt-1.5 text-sm text-muted">
        One full turn in game tells SiegeSense exactly how far your mouse moves your view. Optional, but it makes
        every aim number exact.
      </p>
      {draft.counts_per_360 ? (
        <p className="mt-6 flex items-center gap-2 rounded-xl border border-ok/30 bg-ok/10 px-3.5 py-3 text-sm text-ok">
          <CircleCheck className="size-4" /> Calibrated: {fmtInt(draft.counts_per_360)} counts per 360°
        </p>
      ) : (
        <div className="mt-6">
          <CalibrationPanel
            dpi={draft.dpi}
            onResult={(counts) => {
              update({ counts_per_360: counts });
              onContinue();
            }}
          />
        </div>
      )}
      <div className="mt-4 flex justify-end">
        <Button variant="ghost" size="sm" onClick={onContinue}>
          {draft.counts_per_360 ? "Continue" : "Skip for now"}
        </Button>
      </div>
    </div>
  );
}
