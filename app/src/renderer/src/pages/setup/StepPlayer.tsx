import { Field } from "@/components/ui/Field";
import { type ProfileDraft, validateStep } from "./draft";

type Props = { draft: ProfileDraft; update: (d: ProfileDraft) => void };

export function StepPlayer({ draft, update }: Props) {
  const errors = validateStep("player", draft);
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Who are you in game?</h1>
      <p className="mt-1.5 text-sm text-muted">The coach uses your name to find you in the kill feed.</p>
      <Field
        className="mt-8"
        label="In-game name"
        placeholder="e.g. Ash.Main"
        autoFocus
        maxLength={15}
        value={draft.in_game_name ?? ""}
        error={errors.in_game_name}
        hint="Exactly as it appears in Siege."
        onChange={(e) => update({ in_game_name: e.target.value === "" ? undefined : e.target.value })}
      />
    </div>
  );
}
