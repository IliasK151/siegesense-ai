import type { ReactNode } from "react";
import { useId, useState } from "react";
import { cn } from "@/lib/cn";

type Props = { content: ReactNode; children: ReactNode; side?: "top" | "bottom" | "right"; className?: string };

const sides = {
  top: "bottom-full left-1/2 mb-2 -translate-x-1/2",
  bottom: "top-full left-1/2 mt-2 -translate-x-1/2",
  right: "left-full top-1/2 ml-2 -translate-y-1/2",
};

export function Tooltip({ content, children, side = "top", className }: Props) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span
      className={cn("relative inline-flex", className)}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      aria-describedby={open ? id : undefined}
    >
      {children}
      {open && (
        <span
          id={id}
          role="tooltip"
          className={cn(
            "pointer-events-none absolute z-50 w-max max-w-64 rounded-lg border border-border bg-surface-2 px-3 py-2",
            "text-xs leading-relaxed text-text shadow-xl shadow-black/40",
            sides[side],
          )}
        >
          {content}
        </span>
      )}
    </span>
  );
}
