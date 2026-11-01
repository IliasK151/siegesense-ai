import type { InputHTMLAttributes, ReactNode } from "react";
import { useId } from "react";
import { cn } from "@/lib/cn";

type Props = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: ReactNode;
  error?: string;
  suffix?: ReactNode;
  badge?: ReactNode;
};

export function Field({ label, hint, error, suffix, badge, className, id, ...rest }: Props) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const msgId = `${inputId}-msg`;
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={inputId} className="truncate text-sm font-medium text-text">
        {label}
      </label>
      <div
        className={cn(
          "flex h-11 items-center rounded-xl border bg-surface-2 px-3.5 transition-colors duration-[var(--duration-fast)]",
          "focus-within:border-accent focus-within:shadow-[0_0_0_3px_color-mix(in_srgb,var(--color-accent)_18%,transparent)]",
          error ? "border-error" : "border-border",
        )}
      >
        <input
          id={inputId}
          aria-invalid={error ? true : undefined}
          aria-describedby={error || hint ? msgId : undefined}
          className="min-w-0 flex-1 bg-transparent text-sm text-text outline-none placeholder:text-muted/60"
          {...rest}
        />
        {badge && <span className="ml-2 shrink-0">{badge}</span>}
        {suffix && <span className="ml-2 text-xs text-muted">{suffix}</span>}
      </div>
      {error ? (
        <p id={msgId} role="alert" className="text-xs text-error">
          {error}
        </p>
      ) : (
        hint && (
          <p id={msgId} className="text-xs text-muted">
            {hint}
          </p>
        )
      )}
    </div>
  );
}
