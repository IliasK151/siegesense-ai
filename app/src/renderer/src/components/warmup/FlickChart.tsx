import type { Flick } from "@shared/protocol";

const W = 520;
const H = 170;
const PAD = { l: 34, r: 12, t: 12, b: 22 };

/** Aim position along the flick direction over time: the hump past the target is the overshoot. */
export function FlickChart({ flick }: { flick: Flick }) {
  const pts = flick.trace;
  if (pts.length < 2) return null;
  const tMax = pts[pts.length - 1]![0] || 1;
  const pMax = Math.max(flick.amplitude, ...pts.map((p) => p[1])) * 1.12;
  const pMin = Math.min(0, ...pts.map((p) => p[1]));
  const x = (t: number) => PAD.l + (t / tMax) * (W - PAD.l - PAD.r);
  const y = (p: number) => PAD.t + (1 - (p - pMin) / (pMax - pMin || 1)) * (H - PAD.t - PAD.b);
  const peakIdx = pts.reduce((best, p, i) => (p[1] > pts[best]![1] ? i : best), 0);
  const line = (from: number, to: number) =>
    pts
      .slice(from, to + 1)
      .map(([t, p], i) => `${i ? "L" : "M"}${x(t).toFixed(1)},${y(p).toFixed(1)}`)
      .join(" ");
  const settle = pts[pts.length - 1]![1];

  return (
    <svg data-testid="flick-chart" viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Last flick">
      <line x1={PAD.l} x2={W - PAD.r} y1={y(settle)} y2={y(settle)} stroke="var(--color-border)" strokeDasharray="4 4" />
      <text x={PAD.l - 6} y={y(settle) + 4} textAnchor="end" className="fill-muted text-[10px]">
        {settle.toFixed(0)}°
      </text>
      <text x={PAD.l} y={H - 6} className="fill-muted text-[10px]">
        0 ms
      </text>
      <text x={W - PAD.r} y={H - 6} textAnchor="end" className="fill-muted text-[10px]">
        {Math.round(tMax)} ms
      </text>
      <path d={line(0, peakIdx)} fill="none" stroke="var(--color-accent)" strokeWidth="2.5" strokeLinecap="round" />
      <path
        d={line(peakIdx, pts.length - 1)}
        fill="none"
        stroke={flick.corrected ? "var(--color-warn)" : "var(--color-accent)"}
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      {flick.corrected && (
        <g>
          <circle cx={x(pts[peakIdx]![0])} cy={y(pts[peakIdx]![1])} r="4" fill="var(--color-warn)" />
          <text x={x(pts[peakIdx]![0]) + 8} y={y(pts[peakIdx]![1]) - 6} className="fill-warn text-[11px] font-medium">
            {flick.reversal.toFixed(1)}° past target
          </text>
        </g>
      )}
    </svg>
  );
}
