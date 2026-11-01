import { Check } from "lucide-react";
import { cn } from "@/lib/cn";

export function Stepper({ steps, current }: { steps: readonly string[]; current: number }) {
  return (
    <ol className="flex items-center gap-2" aria-label="Setup progress">
      {steps.map((step, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <li key={step} className="flex items-center gap-2" aria-current={active ? "step" : undefined}>
            <span
              className={cn(
                "flex size-6 items-center justify-center rounded-full border text-[11px] font-semibold transition-colors duration-[var(--duration-base)]",
                done && "border-accent bg-accent text-bg",
                active && "border-accent text-accent",
                !done && !active && "border-border text-muted",
              )}
            >
              {done ? <Check className="size-3.5" /> : i + 1}
            </span>
            <span className={cn("text-xs", active ? "text-text" : "text-muted")}>{step}</span>
            {i < steps.length - 1 && (
              <span className={cn("h-px w-6 transition-colors", done ? "bg-accent" : "bg-border")} />
            )}
          </li>
        );
      })}
    </ol>
  );
}
