import type { RoundSummary } from "@shared/protocol";
import { Skull } from "lucide-react";
import { cn } from "@/lib/cn";

export function RoundStrip({ rounds }: { rounds: RoundSummary[] }) {
  return (
    <div data-testid="round-strip" className="flex flex-wrap gap-2">
      {rounds.map((r) => {
        const label = r.result === "win" ? "W" : r.result === "loss" ? "L" : "–";
        return (
          <div
            key={r.number}
            data-testid={`round-${r.number}`}
            aria-label={`Round ${r.number}: ${r.result ?? "no result"}, ${r.kills} kills${r.died ? ", died" : ""}`}
            className={cn(
              "flex w-14 flex-col items-center rounded-xl border px-2 py-2",
              r.result === "win" && "border-ok/40 bg-ok/10",
              r.result === "loss" && "border-error/40 bg-error/10",
              !r.result && "border-border bg-surface-2",
            )}
          >
            <span className="text-[10px] text-muted">R{r.number}</span>
            <span className="font-mono text-lg font-semibold">{label}</span>
            <span className="flex items-center gap-1 font-mono text-[11px] text-muted">
              {r.kills}K{r.died && <Skull className="size-3 text-error" />}
            </span>
          </div>
        );
      })}
      {rounds.length === 0 && <p className="text-sm text-muted">Rounds appear here as they finish.</p>}
    </div>
  );
}
