import type { Invoice } from "@/lib/api";
import { formatInr } from "@/lib/utils";

/** The exact Tally posting derived by classify — read-only. */
export function JournalPreview({ invoice }: { invoice: Invoice }) {
  if (invoice.journal.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-sm text-muted">
        Recompute to see the journal entry.
      </p>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-surface-muted text-left text-xs uppercase tracking-wide text-muted-2">
            <th className="px-3 py-2 font-medium">Ledger</th>
            <th className="px-3 py-2 text-right font-medium">Debit</th>
            <th className="px-3 py-2 text-right font-medium">Credit</th>
          </tr>
        </thead>
        <tbody>
          {invoice.journal.map((j, i) => (
            <tr key={i} className="border-b border-border last:border-0">
              <td className="px-3 py-2 text-fg">{j.ledger}</td>
              <td className="tabular px-3 py-2 text-right text-fg">
                {j.debit ? formatInr(j.debit) : "—"}
              </td>
              <td className="tabular px-3 py-2 text-right text-fg">
                {j.credit ? formatInr(j.credit) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
