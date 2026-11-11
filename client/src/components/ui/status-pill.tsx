import { cn } from "@/lib/utils";
import type { Exception_, Invoice } from "@/lib/api";

export type ReviewStatus = "clean" | "warning" | "error";

const STYLES: Record<ReviewStatus, string> = {
  clean: "bg-success-bg text-success-fg",
  warning: "bg-warning-bg text-warning-fg",
  error: "bg-danger-bg text-danger-fg",
};

const LABELS: Record<ReviewStatus, string> = {
  clean: "Clean",
  warning: "Warnings",
  error: "Errors",
};

/** Derive a review status from an invoice's exceptions. */
export function reviewStatus(exceptions: Exception_[]): ReviewStatus {
  if (exceptions.some((e) => e.severity === "error")) return "error";
  if (exceptions.some((e) => e.severity === "warning")) return "warning";
  return "clean";
}

export function StatusPill({
  status,
  className,
}: {
  status: ReviewStatus;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        STYLES[status],
        className
      )}
    >
      {LABELS[status]}
    </span>
  );
}

export function InvoiceStatusPill({ invoice }: { invoice: Invoice }) {
  return <StatusPill status={reviewStatus(invoice.exceptions)} />;
}
