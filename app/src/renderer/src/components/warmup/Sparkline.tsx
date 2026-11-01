import type { HistoryPoint } from "@shared/protocol";

export function Sparkline({ points, width = 220, height = 48 }: { points: HistoryPoint[]; width?: number; height?: number }) {
  const scored = points.filter((p) => p.score !== null) as { started_at: string; score: number }[];
  if (scored.length < 2) {
    return <p className="text-xs text-muted">Your score trend appears after two scored warm-ups.</p>;
  }
  const x = (i: number) => 4 + (i / (scored.length - 1)) * (width - 8);
  const y = (s: number) => 4 + (1 - s / 100) * (height - 8);
  const d = scored.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.score).toFixed(1)}`).join(" ");
  const last = scored[scored.length - 1]!;
  return (
    <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} role="img" aria-label="Score trend">
      <path d={d} fill="none" stroke="var(--color-accent)" strokeWidth="2" strokeLinejoin="round" />
      <circle cx={x(scored.length - 1)} cy={y(last.score)} r="3.5" fill="var(--color-accent)" />
    </svg>
  );
}
