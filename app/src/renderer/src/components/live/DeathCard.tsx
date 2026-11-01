import type { LiveEvent, RoundSummary } from "@shared/protocol";
import { Skull } from "lucide-react";
import { Badge } from "@/components/ui/Badge";

export function DeathCard({ event, round }: { event: LiveEvent; round?: RoundSummary }) {
  const d = event.data as { killer?: string; time_alive_s?: number; first_death?: boolean };
  return (
    <article data-testid="death-card" className="overflow-hidden rounded-[var(--radius-card)] border border-border bg-surface">
      {event.clip ? (
        // biome-ignore lint/a11y/useMediaCaption: gameplay clip without speech
        <video src={`clip://media/${event.clip}`} controls preload="metadata" className="aspect-video w-full bg-black" />
      ) : (
        <div className="flex aspect-video items-center justify-center bg-surface-2 text-sm text-muted">No clip</div>
      )}
      <div className="flex flex-col gap-2 p-4">
        <p className="flex items-center gap-2 font-medium">
          <Skull className="size-4 text-error" /> Round {event.round} · Killed by {d.killer ?? "unknown"}
        </p>
        <div className="flex flex-wrap gap-1.5">
          {d.time_alive_s != null && <Badge>{d.time_alive_s.toFixed(1)} s alive</Badge>}
          {d.first_death && <Badge tone="warn">First death</Badge>}
          {round?.traded && <Badge tone="ok">Traded</Badge>}
          {round && !round.traded && round.died && <Badge tone="error">Not traded</Badge>}
          {event.confidence === "low" && <Badge>Unsure</Badge>}
        </div>
      </div>
    </article>
  );
}
