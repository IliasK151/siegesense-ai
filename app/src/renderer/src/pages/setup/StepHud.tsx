import { DEFAULT_HUD_REGIONS } from "@shared/protocol";
import { HudCheck } from "@/components/hud/HudCheck";
import { Button } from "@/components/ui/Button";
import type { ProfileDraft } from "./draft";

type Props = { draft: ProfileDraft; update: (d: ProfileDraft) => void; onContinue: () => void };

export function StepHud({ draft, update, onContinue }: Props) {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Check your HUD</h1>
      <p className="mt-1.5 text-sm text-muted">
        Show SiegeSense where the kill feed, timer, score and your health are. Optional — you can do it later in
        Settings.
      </p>
      <div className="mt-6">
        <HudCheck
          regions={draft.hud_regions ?? DEFAULT_HUD_REGIONS}
          side={draft.my_score_side ?? "left"}
          inGameName={draft.in_game_name}
          onSave={(hud_regions, my_score_side) => {
            update({ hud_regions, my_score_side });
            onContinue();
          }}
        />
      </div>
      <div className="mt-2 flex justify-start">
        <Button variant="ghost" size="sm" onClick={onContinue}>
          Skip HUD check
        </Button>
      </div>
    </div>
  );
}
