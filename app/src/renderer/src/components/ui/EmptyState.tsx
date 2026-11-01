import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export function EmptyState({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-[var(--radius-card)] border border-dashed border-border bg-surface/50 px-8 py-20 text-center">
      <span className="mb-4 flex size-12 items-center justify-center rounded-2xl border border-border bg-surface-2">
        <Icon className="size-5 text-accent" />
      </span>
      <p className="text-base font-semibold">{title}</p>
      <p className="mt-1.5 max-w-sm text-sm text-muted">{children}</p>
    </div>
  );
}
