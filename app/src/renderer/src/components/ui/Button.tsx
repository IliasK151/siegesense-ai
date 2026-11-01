import type { LucideIcon } from "lucide-react";
import { LoaderCircle } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md" | "lg";
  icon?: LucideIcon;
  loading?: boolean;
};

const variants = {
  primary:
    "bg-accent text-bg font-semibold hover:bg-accent-strong hover:shadow-[0_0_24px_-4px_var(--color-accent)] active:scale-[0.98]",
  secondary: "bg-surface-2 text-text border border-border hover:border-muted/60 hover:bg-border/60",
  ghost: "text-muted hover:text-text hover:bg-surface-2",
};
const sizes = {
  sm: "h-8 px-3 text-xs gap-1.5 rounded-lg",
  md: "h-10 px-4 text-sm gap-2 rounded-xl",
  lg: "h-14 px-6 text-base gap-2.5 rounded-xl",
};

export function Button({ variant = "secondary", size = "md", icon: Icon, loading, disabled, className, children, ...rest }: Props) {
  return (
    <button
      type="button"
      disabled={disabled || loading}
      className={cn(
        "no-drag inline-flex items-center justify-center whitespace-nowrap transition-all duration-[var(--duration-fast)]",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
        "disabled:pointer-events-none disabled:opacity-40",
        variants[variant],
        sizes[size],
        className,
      )}
      {...rest}
    >
      {loading ? <LoaderCircle className="size-4 animate-spin" /> : Icon && <Icon className="size-4" />}
      {children}
    </button>
  );
}
