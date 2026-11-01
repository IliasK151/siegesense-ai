import { LIGHT_KEYS } from "@shared/protocol";
import { ChartLine, Clapperboard, House, type LucideIcon, Radio, Settings } from "lucide-react";
import { StatusLight } from "@/components/ui/StatusLight";
import { cn } from "@/lib/cn";
import { useStatus } from "@/lib/engineContext";
import { type Page, useNav } from "@/store/nav";

const items: { page: Page; label: string; icon: LucideIcon }[] = [
  { page: "home", label: "Home", icon: House },
  { page: "live", label: "Live", icon: Radio },
  { page: "review", label: "Review", icon: Clapperboard },
  { page: "progress", label: "Progress", icon: ChartLine },
  { page: "settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const { page, go } = useNav();
  const status = useStatus();
  return (
    <nav className="flex w-56 shrink-0 flex-col border-r border-border/60 bg-bg px-3 py-4">
      <ul className="flex flex-col gap-1">
        {items.map(({ page: p, label, icon: Icon }) => {
          const active = page === p;
          return (
            <li key={p}>
              <button
                type="button"
                onClick={() => go(p)}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "relative flex h-10 w-full items-center gap-3 rounded-xl px-3 text-sm transition-colors duration-[var(--duration-fast)]",
                  active ? "bg-surface-2 text-text" : "text-muted hover:bg-surface hover:text-text",
                )}
              >
                {active && <span className="absolute left-0 top-2 bottom-2 w-[3px] rounded-full bg-accent" />}
                <Icon className={cn("size-4", active && "text-accent")} />
                {label}
              </button>
            </li>
          );
        })}
      </ul>
      <div className="mt-auto rounded-xl border border-border/60 bg-surface px-3 py-2.5">
        <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">System</p>
        <div className="flex items-center gap-1">
          {status
            ? LIGHT_KEYS.map((k) => <StatusLight key={k} lightKey={k} light={status.lights[k]} compact />)
            : <span className="text-xs text-muted">Connecting…</span>}
        </div>
      </div>
    </nav>
  );
}
