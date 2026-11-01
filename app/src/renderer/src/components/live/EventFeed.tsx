import type { LiveEvent } from "@shared/protocol";
import { Crosshair, Flag, Repeat, Skull, Timer, Trophy } from "lucide-react";
import { cn } from "@/lib/cn";
import { describeEvent } from "./describe";

const icons = { round_start: Flag, phase: Timer, kill: Crosshair, death: Skull, round_end: Trophy, repeek: Repeat };
const tones = {
  round_start: "text-muted",
  phase: "text-muted",
  kill: "text-ok",
  death: "text-error",
  round_end: "text-text",
  repeek: "text-warn",
};

export function EventFeed({ events }: { events: LiveEvent[] }) {
  const recent = [...events].reverse().slice(0, 40);
  return (
    <ul data-testid="event-feed" className="flex flex-col gap-1">
      {recent.map((e, i) => {
        const Icon = icons[e.kind];
        const low = e.confidence === "low";
        return (
          <li
            key={`${e.kind}-${e.t}-${i}`}
            className={cn("flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm", low && "opacity-50")}
          >
            <Icon className={cn("size-4 shrink-0", tones[e.kind])} />
            <span className="flex-1">{describeEvent(e)}</span>
            {low && <span className="text-xs text-muted">(unsure)</span>}
            <span className="font-mono text-[11px] text-muted">R{e.round}</span>
          </li>
        );
      })}
      {recent.length === 0 && (
        <li className="py-8 text-center text-sm text-muted">Waiting for the round to start…</li>
      )}
    </ul>
  );
}
