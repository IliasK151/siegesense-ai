import { Profile } from "@shared/protocol";
import { CircleAlert } from "lucide-react";
import { ProfileSummary } from "../ProfileSummary";
import type { ProfileDraft } from "./draft";

export function StepDone({ draft, error }: { draft: ProfileDraft; error: string | null }) {
  const parsed = Profile.safeParse(draft);
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">You're all set{draft.in_game_name ? `, ${draft.in_game_name}` : ""}</h1>
      <p className="mt-1.5 text-sm text-muted">Check everything looks right, then save your profile.</p>
      <div className="mt-8">{parsed.success && <ProfileSummary profile={parsed.data} />}</div>
      {error && (
        <p role="alert" className="mt-5 flex items-start gap-2 rounded-xl border border-error/30 bg-error/10 px-3.5 py-3 text-sm text-error">
          <CircleAlert className="mt-0.5 size-4 shrink-0" />
          <span>{error}</span>
        </p>
      )}
    </div>
  );
}
