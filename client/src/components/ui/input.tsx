import { forwardRef } from "react";
import { cn } from "@/lib/utils";

export const Input = forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm text-fg",
      "placeholder:text-muted-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-brand",
      "disabled:opacity-50",
      className
    )}
    {...props}
  />
));
Input.displayName = "Input";
