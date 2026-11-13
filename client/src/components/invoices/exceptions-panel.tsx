import { AlertTriangle, CircleAlert, Info, Lightbulb } from "lucide-react";

import type { Invoice, Severity } from "@/lib/api";
import { cn } from "@/lib/utils";

const SEV: Record<Severity, { bg: string; fg: string; Icon: typeof Info }> = {
  error: { bg: "bg-danger-bg", fg: "text-danger-fg", Icon: CircleAlert },
  warning: { bg: "bg-warning-bg", fg: "text-warning-fg", Icon: AlertTriangle },
  info: { bg: "bg-info-bg", fg: "text-info-fg", Icon: Info },
};

/** The trust surface: what the machine flagged (exceptions) and inferred
 *  (assumptions). Shown above the reading so a reviewer sees it first. */
export function ExceptionsPanel({ invoice }: { invoice: Invoice }) {
  const { exceptions, assumptions } = invoice;
  if (exceptions.length === 0 && assumptions.length === 0) return null;

  return (
    <div className="space-y-2">
      {exceptions.map((e, i) => {
        const s = SEV[e.severity];
        return (
          <div
            key={`e${i}`}
            className={cn(
              "flex gap-2 rounded-lg px-3 py-2 text-sm",
              s.bg,
              s.fg
            )}
          >
            <s.Icon className="mt-0.5 size-4 shrink-0" />
            <p>
              <span className="font-medium">{e.code}</span> — {e.message}
            </p>
          </div>
        );
      })}
      {assumptions.map((a, i) => (
        <div
          key={`a${i}`}
          className="flex gap-2 rounded-lg bg-surface-muted px-3 py-2 text-sm text-muted"
        >
          <Lightbulb className="mt-0.5 size-4 shrink-0 text-muted-2" />
          <p>
            <span className="font-medium text-fg">{a.field}</span> — {a.value}.{" "}
            {a.reason}
          </p>
        </div>
      ))}
    </div>
  );
}
