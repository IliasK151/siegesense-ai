import type { MatchSummary } from "@shared/protocol";
import { RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { RoundStrip } from "./RoundStrip";

export function MatchSummaryView({ summary, onAgain }: { summary: MatchSummary; onAgain: () => void }) {
  const won = summary.rounds.filter((r) => r.result === "win").length;
  const lost = summary.rounds.filter((r) => r.result === "loss").length;
  const stats = [
    ["Rounds", `${won}–${lost}`, "rounds"],
    ["Deaths", summary.deaths.length, "deaths"],
    ["First deaths", summary.rounds.filter((r) => r.first_death).length, "first-deaths"],
    ["Traded deaths", summary.rounds.filter((r) => r.died && r.traded).length, "traded"],
    ["Kills", summary.rounds.reduce((n, r) => n + r.kills, 0), "kills"],
    ["Re-peeks", summary.rounds.reduce((n, r) => n + r.repeeks, 0), "repeeks"],
  ] as const;
  return (
    <div data-testid="match-summary" className="flex flex-col gap-5">
      <Card title="Match summary">
        <dl className="grid grid-cols-6 gap-2.5">
          {stats.map(([label, value, id]) => (
            <div key={id} className="rounded-xl bg-surface-2 px-3.5 py-3">
              <dt className="text-[11px] uppercase tracking-[0.12em] text-muted">{label}</dt>
              <dd data-testid={`stat-${id}`} className="mt-1 font-mono text-xl font-semibold">
                {value}
              </dd>
            </div>
          ))}
        </dl>
        <div className="mt-5">
          <RoundStrip rounds={summary.rounds} />
        </div>
        <div className="mt-6">
          <Button variant="primary" icon={RotateCcw} onClick={onAgain}>
            Back to Live Mode
          </Button>
        </div>
      </Card>
    </div>
  );
}
