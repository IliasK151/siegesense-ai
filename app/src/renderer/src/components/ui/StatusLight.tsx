import type { Light, LightKey } from "@shared/protocol";
import { cn } from "@/lib/cn";
import { Tooltip } from "./Tooltip";

const dot = {
  ok: "bg-ok shadow-[0_0_10px_var(--color-ok)]",
  warn: "bg-warn shadow-[0_0_10px_var(--color-warn)]",
  error: "bg-error shadow-[0_0_10px_var(--color-error)]",
  off: "bg-border",
};

type Props = { lightKey: LightKey; light: Light; compact?: boolean };

function Dot({ light }: { light: Light }) {
  const pulsing = light.state === "warn" || light.state === "error";
  return (
    <span className="relative flex size-2.5 shrink-0">
      {pulsing && <span className={cn("absolute inset-0 animate-ping rounded-full opacity-60", dot[light.state])} />}
      <span className={cn("relative size-2.5 rounded-full", dot[light.state])} />
    </span>
  );
}

export function StatusLight({ lightKey, light, compact }: Props) {
  const tip = (
    <>
      <span className="block font-medium">{light.label}</span>
      <span className="block text-muted">{light.detail}</span>
      {light.fix && <span className="mt-1 block text-accent">→ {light.fix}</span>}
    </>
  );
  return (
    <Tooltip content={tip} side={compact ? "right" : "top"}>
      <span
        tabIndex={0}
        data-testid={compact ? "status-dot" : "status-light"}
        data-key={lightKey}
        aria-label={`${light.label}: ${light.detail}`}
        className={cn(
          "flex items-center gap-2.5 rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-accent",
          compact ? "p-1" : "w-full",
        )}
      >
        <Dot light={light} />
        {!compact && (
          <span className={cn("truncate text-sm", light.state === "off" ? "text-muted" : "text-text")}>{light.label}</span>
        )}
      </span>
    </Tooltip>
  );
}
