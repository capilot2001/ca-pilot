import { cn } from "@/lib/utils";

/** Shimmer placeholder. Compose these into page-shaped loading states. */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-surface-muted", className)}
      aria-hidden
    />
  );
}
