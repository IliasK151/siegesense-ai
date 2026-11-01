import { type GameSettingsImport, Profile } from "@shared/protocol";
import { ArrowLeft, ArrowRight, Save } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Stepper } from "@/components/ui/Stepper";
import { EngineError } from "@/lib/engineClient";
import { useEngine, useProfile } from "@/lib/engineContext";
import { useNav } from "@/store/nav";
import { type ProfileDraft, sanitizeImport, stepIsValid, WIZARD_STEPS, type WizardStep } from "./draft";
import type { ImportInfo } from "./ImportBadge";
import { StepCalibrate } from "./StepCalibrate";
import { StepDisplay } from "./StepDisplay";
import { StepDone } from "./StepDone";
import { StepHud } from "./StepHud";
import { StepPlayer } from "./StepPlayer";
import { StepSensitivity } from "./StepSensitivity";
import { StepWelcome } from "./StepWelcome";

const CALIBRATE_STEP = WIZARD_STEPS.indexOf("Calibrate");
const HUD_STEP = WIZARD_STEPS.indexOf("HUD");
const VALIDATED: (WizardStep | null)[] = [null, "player", "sensitivity", null, "display", null, null];

/** A calibration only holds for the sensitivity it was measured with. */
function withCalibrationCheck(prev: ProfileDraft, next: ProfileDraft): ProfileDraft {
  const changed =
    prev.yaw_sensitivity !== next.yaw_sensitivity || prev.mouse_multiplier_unit !== next.mouse_multiplier_unit;
  return changed && next.counts_per_360 ? { ...next, counts_per_360: undefined } : next;
}

export function SetupWizard() {
  const engine = useEngine();
  const { profile, reload } = useProfile();
  const go = useNav((s) => s.go);
  const [step, setStep] = useState(0);
  const [dir, setDir] = useState(1);
  const [draft, setDraft] = useState<ProfileDraft>(() => ({ ...(profile ?? {}) }));
  const [importInfo, setImportInfo] = useState<ImportInfo | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const update = (d: ProfileDraft) => setDraft((prev) => withCalibrationCheck(prev, { ...prev, ...d }));
  const onImported = (r: GameSettingsImport) => {
    const { values, missing } = sanitizeImport(r.values, r.missing);
    setDraft((prev) => {
      const next = withCalibrationCheck(prev, { ...prev, ...values });
      // Clear fields the file had with invalid values; keep anything the file simply lacked.
      for (const field of Object.keys(r.values)) {
        if (!(field in values)) delete next[field as keyof ProfileDraft];
      }
      return next;
    });
    setImportInfo({ imported: new Set(Object.keys(values)), missing: new Set(missing) });
  };

  const gate = VALIDATED[step];
  const canNext = gate ? stepIsValid(gate, draft) : true;
  const isLast = step === WIZARD_STEPS.length - 1;
  const move = (delta: number) => {
    setDir(delta);
    setStep((s) => s + delta);
  };

  async function save() {
    setSaving(true);
    setSaveError(null);
    try {
      const parsed = Profile.parse(draft);
      await engine.request("save_profile", { profile: parsed });
      await reload();
      go("home");
    } catch (err) {
      setSaveError(err instanceof EngineError ? err.message : "Some values are invalid. Go back and check them.");
    } finally {
      setSaving(false);
    }
  }

  const body = [
    <StepWelcome key="welcome" />,
    <StepPlayer key="player" draft={draft} update={update} />,
    <StepSensitivity key="sens" draft={draft} update={update} importInfo={importInfo} onImported={onImported} />,
    <StepCalibrate key="cal" draft={draft} update={update} onContinue={() => move(1)} />,
    <StepDisplay key="display" draft={draft} update={update} importInfo={importInfo} />,
    <StepHud key="hud" draft={draft} update={update} onContinue={() => move(1)} />,
    <StepDone key="done" draft={draft} error={saveError} />,
  ][step];

  return (
    <div data-testid="setup-wizard" className="flex min-h-0 flex-1 flex-col items-center overflow-y-auto px-6 py-10">
      <div className={step === HUD_STEP ? "w-full max-w-5xl" : "w-full max-w-2xl"}>
        <div className="mb-8 flex justify-center">
          <Stepper steps={WIZARD_STEPS} current={step} />
        </div>
        <div className="overflow-hidden rounded-[var(--radius-card)] border border-border bg-surface p-8">
          <motion.div
            key={step}
            initial={{ opacity: 0, x: 24 * dir }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
          >
            {body}
          </motion.div>
          <footer className="mt-10 flex items-center justify-between border-t border-border pt-5">
            {step > 0 ? (
              <Button variant="ghost" icon={ArrowLeft} onClick={() => move(-1)} disabled={saving}>
                Back
              </Button>
            ) : profile ? (
              <Button variant="ghost" onClick={() => go("home")}>
                Cancel
              </Button>
            ) : (
              <span />
            )}
            {step === 0 ? (
              <Button variant="primary" onClick={() => move(1)}>
                Get started <ArrowRight className="size-4" />
              </Button>
            ) : isLast ? (
              <Button variant="primary" icon={Save} loading={saving} onClick={save}>
                Save profile
              </Button>
            ) : step === CALIBRATE_STEP || step === HUD_STEP ? (
              <span />
            ) : (
              <Button variant="primary" onClick={() => move(1)} disabled={!canNext}>
                Next <ArrowRight className="size-4" />
              </Button>
            )}
          </footer>
        </div>
      </div>
    </div>
  );
}
