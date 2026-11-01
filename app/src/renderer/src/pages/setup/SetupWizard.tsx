import { type GameSettingsImport, Profile } from "@shared/protocol";
import { ArrowLeft, ArrowRight, Save } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Stepper } from "@/components/ui/Stepper";
import { EngineError } from "@/lib/engineClient";
import { useEngine, useProfile } from "@/lib/engineContext";
import { useNav } from "@/store/nav";
import { type ProfileDraft, stepIsValid, WIZARD_STEPS, type WizardStep } from "./draft";
import type { ImportInfo } from "./ImportBadge";
import { StepDisplay } from "./StepDisplay";
import { StepDone } from "./StepDone";
import { StepPlayer } from "./StepPlayer";
import { StepSensitivity } from "./StepSensitivity";
import { StepWelcome } from "./StepWelcome";

const VALIDATED: (WizardStep | null)[] = [null, "player", "sensitivity", "display", null];

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

  const update = (d: ProfileDraft) => setDraft((prev) => ({ ...prev, ...d }));
  const onImported = (r: GameSettingsImport) => {
    setDraft((prev) => ({ ...prev, ...r.values }));
    setImportInfo({ imported: new Set(Object.keys(r.values)), missing: new Set(r.missing) });
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
    <StepDisplay key="display" draft={draft} update={update} importInfo={importInfo} />,
    <StepDone key="done" draft={draft} error={saveError} />,
  ][step];

  return (
    <div data-testid="setup-wizard" className="flex min-h-0 flex-1 flex-col items-center overflow-y-auto px-6 py-10">
      <div className="w-full max-w-2xl">
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
