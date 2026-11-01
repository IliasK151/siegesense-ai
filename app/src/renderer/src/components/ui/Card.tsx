import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";

type Props = Omit<HTMLAttributes<HTMLElement>, "title"> & { title?: ReactNode; action?: ReactNode };

export function Card({ title, action, className, children, ...rest }: Props) {
  return (
    <section className={cn("rounded-[var(--radius-card)] border border-border bg-surface p-5", className)} {...rest}>
      {(title || action) && (
        <header className="mb-4 flex items-center justify-between gap-3">
          {title && <h2 className="text-xs font-semibold uppercase tracking-[0.12em] text-muted">{title}</h2>}
          {action}
        </header>
      )}
      {children}
    </section>
  );
}
