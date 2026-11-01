import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

type Props = { label: string; value: ReactNode; hint?: string; big?: boolean; testId?: string; tone?: "accent" };

export function MetricTile({ label, value, hint, big, testId, tone }: Props) {
  return (
    <div
      className={cn(
        "flex flex-col justify-between rounded-[var(--radius-card)] border border-border bg-surface p-4",
        big && "row-span-2 p-6",
        tone === "accent" && "border-accent/40 bg-gradient-to-br from-accent/10 to-transparent",
      )}
    >
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">{label}</p>
      <p
        data-testid={testId}
        className={cn("font-mono font-semibold tabular-nums", big ? "text-6xl text-accent" : "mt-2 text-2xl")}
      >
        {value}
      </p>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  );
}
