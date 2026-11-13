import type { ReconLine, ReconStatus } from "@/lib/api";
import { cn, formatInr } from "@/lib/utils";

const STATUS: Record<ReconStatus, { label: string; cls: string }> = {
  matched: { label: "Matched", cls: "bg-success-bg text-success-fg" },
  value_mismatch: { label: "Value mismatch", cls: "bg-danger-bg text-danger-fg" },
  only_in_books: { label: "Only in books", cls: "bg-warning-bg text-warning-fg" },
  only_in_2a: { label: "Only in 2A", cls: "bg-info-bg text-info-fg" },
};

function ReconStatusPill({ status }: { status: ReconStatus }) {
  const s = STATUS[status];
  return (
    <span
      className={cn(
        "inline-flex whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium",
        s.cls
      )}
    >
      {s.label}
    </span>
  );
}

export function ReconTable({ lines }: { lines: ReconLine[] }) {
  if (lines.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-border px-6 py-10 text-center text-sm text-muted">
        Nothing to reconcile yet.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full min-w-[760px] text-sm">
        <thead>
          <tr className="border-b border-border bg-surface-muted text-left text-xs uppercase tracking-wide text-muted-2">
            <th className="px-3 py-2.5 font-medium">Party</th>
            <th className="px-3 py-2.5 font-medium">Invoice</th>
            <th className="px-3 py-2.5 font-medium">Status</th>
            <th className="px-3 py-2.5 text-right font-medium">Books tax</th>
            <th className="px-3 py-2.5 text-right font-medium">2A tax</th>
            <th className="px-3 py-2.5 text-right font-medium">Diff</th>
          </tr>
        </thead>
        <tbody>
          {lines.map((l, i) => (
            <tr key={i} className="border-b border-border align-top last:border-0">
              <td className="px-3 py-2.5">
                <div className="font-medium text-fg">{l.party_name || "—"}</div>
                {l.party_gstin && (
                  <div className="text-xs text-muted-2">{l.party_gstin}</div>
                )}
              </td>
              <td className="px-3 py-2.5">
                <div className="text-fg">{l.invoice_number || "—"}</div>
                {l.invoice_date && (
                  <div className="text-xs text-muted-2">{l.invoice_date}</div>
                )}
              </td>
              <td className="px-3 py-2.5">
                <ReconStatusPill status={l.status} />
                {l.diffs.length > 0 && (
                  <div className="mt-1 max-w-56 text-xs text-muted">
                    {l.diffs.join("; ")}
                  </div>
                )}
              </td>
              <td className="tabular px-3 py-2.5 text-right text-fg">
                {formatInr(l.books_tax)}
              </td>
              <td className="tabular px-3 py-2.5 text-right text-fg">
                {formatInr(l.gstr2a_tax)}
              </td>
              <td
                className={cn(
                  "tabular px-3 py-2.5 text-right font-medium",
                  Math.abs(l.tax_diff) > 0.01 ? "text-danger-fg" : "text-muted"
                )}
              >
                {l.tax_diff ? formatInr(l.tax_diff) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
