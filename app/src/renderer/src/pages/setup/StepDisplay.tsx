import type { WindowMode } from "@shared/protocol";
import { CircleCheck, TriangleAlert } from "lucide-react";
import { Field } from "@/components/ui/Field";
import { cn } from "@/lib/cn";
import { type ProfileDraft, toNumber, validateStep } from "./draft";
import { ImportBadge, type ImportInfo } from "./ImportBadge";

type Props = { draft: ProfileDraft; update: (d: ProfileDraft) => void; importInfo: ImportInfo | null };
type NumField = "fov" | "resolution_width" | "resolution_height" | "hud_scale";

const MODES: { value: Exclude<WindowMode, "unknown">; label: string }[] = [
  { value: "fullscreen", label: "Fullscreen" },
  { value: "borderless", label: "Borderless" },
  { value: "windowed", label: "Windowed" },
];

export function StepDisplay({ draft, update, importInfo }: Props) {
  const errors = validateStep("display", draft);
  const num = (field: NumField) => ({
    type: "number" as const,
    value: draft[field] ?? "",
    error: errors[field],
    badge: <ImportBadge field={field} info={importInfo} />,
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => update({ [field]: toNumber(e.target.value) }),
  });

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Display</h1>
      <p className="mt-1.5 text-sm text-muted">Used to find the HUD and kill feed on your screen.</p>

      <div className="mt-8 grid grid-cols-2 gap-4">
        <Field label="Resolution width" suffix="px" {...num("resolution_width")} />
        <Field label="Resolution height" suffix="px" {...num("resolution_height")} />
        <Field label="Field of view" placeholder="75" hint="Siege allows 60–90" {...num("fov")} />
        <Field label="HUD scale" suffix="%" hint="100 unless you changed it" {...num("hud_scale")} />
      </div>

      <div className="mt-6">
        <div className="mb-1.5 flex items-center justify-between">
          <p className="text-sm font-medium">Display mode</p>
          <ImportBadge field="window_mode" info={importInfo} />
        </div>
        <div role="radiogroup" aria-label="Display mode" className="grid grid-cols-3 gap-1 rounded-xl bg-surface-2 p-1">
          {MODES.map((m) => (
            <button
              key={m.value}
              type="button"
              role="radio"
              aria-checked={draft.window_mode === m.value}
              onClick={() => update({ window_mode: m.value })}
              className={cn(
                "h-9 rounded-lg text-sm transition-colors duration-[var(--duration-fast)]",
                draft.window_mode === m.value ? "bg-surface text-text shadow" : "text-muted hover:text-text",
              )}
            >
              {m.label}
            </button>
          ))}
        </div>
        {draft.window_mode === "fullscreen" && (
          <p className="mt-3 flex items-start gap-2 rounded-xl border border-warn/30 bg-warn/10 px-3.5 py-3 text-sm text-warn">
            <TriangleAlert className="mt-0.5 size-4 shrink-0" />
            Switch Siege to Borderless so the in-game overlay can show. The voice coach works either way.
          </p>
        )}
        {draft.window_mode === "borderless" && (
          <p className="mt-3 flex items-center gap-2 rounded-xl border border-ok/30 bg-ok/10 px-3.5 py-3 text-sm text-ok">
            <CircleCheck className="size-4 shrink-0" />
            Borderless is perfect — the overlay will show in game.
          </p>
        )}
      </div>
    </div>
  );
}
