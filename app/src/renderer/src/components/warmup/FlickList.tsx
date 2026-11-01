import type { Flick } from "@shared/protocol";
import { Badge } from "@/components/ui/Badge";
import { flickTag } from "./format";

export function FlickList({ flicks }: { flicks: Flick[] }) {
  const recent = flicks.slice(-8).reverse();
  return (
    <ul data-testid="flick-list" className="flex flex-col divide-y divide-border">
      {recent.map((f) => {
        const tag = flickTag(f);
        return (
          <li key={f.id} className="flex items-center justify-between py-2 text-sm">
            <span className="flex items-center gap-3">
              <span className="w-8 font-mono text-xs text-muted">#{f.id}</span>
              <Badge tone={tag.tone}>{tag.label}</Badge>
            </span>
            <span className="font-mono text-xs text-muted">
              {f.amplitude.toFixed(0)}° · {Math.round(f.peak_speed)}°/s
            </span>
          </li>
        );
      })}
      {recent.length === 0 && <li className="py-6 text-center text-sm text-muted">Flick to a target to see it here.</li>}
    </ul>
  );
}
