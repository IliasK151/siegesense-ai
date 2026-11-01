import type { WarmupSummary } from "@shared/protocol";
import { Dumbbell, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { fmtElapsed, pct } from "./format";
import { Sparkline } from "./Sparkline";

export function WarmupSummaryView({ summary, onAgain }: { summary: WarmupSummary; onAgain: () => void }) {
  const m = summary.metrics;
  const recap = [
    ["Flicks", m.flicks],
    ["Overshoot", pct(m.overshoot_rate)],
    ["Corrections", pct(m.correction_rate)],
    ["Avg flick speed", `${Math.round(m.avg_peak_speed)}°/s`],
    ["Shots while moving", pct(m.moving_shot_rate)],
    ["Duration", fmtElapsed(summary.duration_s)],
  ] as const;
  return (
    <div className="grid grid-cols-3 gap-5">
      <Card className="flex flex-col items-center justify-center text-center">
        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Warm-up score</p>
        <p data-testid="summary-score" className="mt-2 font-mono text-7xl font-semibold text-accent">
          {m.score ?? "—"}
        </p>
        <p className="mt-2 text-sm text-muted">{summary.drill ? "See your drill →" : summary.message}</p>
        <div className="mt-5">
          <Sparkline points={summary.history} />
        </div>
      </Card>
      <Card className="col-span-2" title="What to work on">
        {summary.drill ? (
          <div className="flex gap-4">
            <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-accent/10">
              <Dumbbell className="size-5 text-accent" />
            </span>
            <div>
              <p className="text-lg font-semibold">{summary.drill.title}</p>
              <p className="mt-1 text-sm leading-relaxed text-muted">{summary.drill.text}</p>
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted">{summary.message}</p>
        )}
        <dl className="mt-6 grid grid-cols-3 gap-2.5">
          {recap.map(([label, value]) => (
            <div key={label} className="rounded-xl bg-surface-2 px-3.5 py-2.5">
              <dt className="text-[11px] uppercase tracking-[0.12em] text-muted">{label}</dt>
              <dd className="mt-0.5 font-mono font-semibold">{value}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-6">
          <Button variant="primary" icon={RotateCcw} onClick={onAgain}>
            New warm-up
          </Button>
        </div>
      </Card>
    </div>
  );
}
