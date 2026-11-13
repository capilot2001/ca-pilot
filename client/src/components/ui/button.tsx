import { forwardRef } from "react";
import { cn } from "@/lib/utils";

type Variant = "primary" | "outline" | "ghost" | "danger";
type Size = "sm" | "md";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-brand text-brand-fg hover:bg-brand-hover focus-visible:ring-ring",
  outline:
    "border border-border bg-surface text-fg hover:bg-surface-muted focus-visible:ring-ring",
  ghost: "text-fg hover:bg-surface-muted focus-visible:ring-ring",
  danger:
    "bg-danger-bg text-danger-fg hover:brightness-95 focus-visible:ring-danger-fg",
};

const SIZES: Record<Size, string> = {
  sm: "h-8 px-3 text-sm gap-1.5",
  md: "h-10 px-4 text-sm gap-2",
};

/** Shared button styling — also usable on a styled <Link>. */
export function buttonClasses(
  variant: Variant = "primary",
  size: Size = "md",
  className?: string
) {
  return cn(
    "inline-flex items-center justify-center rounded-lg font-medium",
    "transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1",
    "disabled:pointer-events-none disabled:opacity-50",
    VARIANTS[variant],
    SIZES[size],
    className
  );
}

/** Keyboard-shortcut chip for buttons/links. */
export function Kbd({
  children,
  tone = "muted",
}: {
  children: React.ReactNode;
  tone?: "muted" | "onBrand";
}) {
  return (
    <kbd
      className={cn(
        "ml-1 rounded px-1.5 py-0.5 text-[11px] font-semibold",
        tone === "onBrand"
          ? "bg-white/20 text-brand-fg"
          : "bg-surface-muted text-muted"
      )}
    >
      {children}
    </kbd>
  );
}

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  shortcut?: string;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", shortcut, children, ...props }, ref) => (
    <button
      ref={ref}
      className={buttonClasses(variant, size, className)}
      {...props}
    >
      {children}
      {shortcut && (
        <Kbd tone={variant === "primary" ? "onBrand" : "muted"}>{shortcut}</Kbd>
      )}
    </button>
  )
);
Button.displayName = "Button";
