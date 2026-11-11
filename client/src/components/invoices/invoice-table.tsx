"use client";

import { useRouter } from "next/navigation";

import { InvoiceStatusPill } from "@/components/ui/status-pill";
import type { BatchItem } from "@/lib/store/batch";
import { formatInr } from "@/lib/utils";

function dateLabel(i: BatchItem): string {
  return i.invoice.invoice_date_display || i.invoice.invoice_date || "—";
}

function directionLabel(d: string): string {
  if (d === "purchase") return "Purchase";
  if (d === "sale") return "Sale";
  return "Unknown";
}

export function InvoiceTable({ items }: { items: BatchItem[] }) {
  const router = useRouter();

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-2">
            <th className="px-4 py-3 font-medium">Number</th>
            <th className="px-4 py-3 font-medium">Date</th>
            <th className="px-4 py-3 font-medium">Party</th>
            <th className="px-4 py-3 font-medium">Direction</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 text-right font-medium">Total</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const inv = item.invoice;
            return (
              <tr
                key={item.id}
                onClick={() => router.push(`/invoices/${item.id}`)}
                className="cursor-pointer border-b border-border last:border-0 hover:bg-surface-muted"
              >
                <td className="px-4 py-3 font-medium text-fg">
                  {inv.invoice_number || (
                    <span className="text-muted">{inv.source_file}</span>
                  )}
                  {item.dirty && (
                    <span className="ml-2 text-xs font-normal text-warning-fg">
                      edited
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-muted">{dateLabel(item)}</td>
                <td className="px-4 py-3 text-fg">
                  {inv.party_name || <span className="text-muted-2">—</span>}
                </td>
                <td className="px-4 py-3 text-muted">
                  {directionLabel(inv.direction)}
                </td>
                <td className="px-4 py-3">
                  <InvoiceStatusPill invoice={inv} />
                </td>
                <td className="tabular px-4 py-3 text-right font-medium text-fg">
                  {formatInr(inv.invoice_total || inv.taxable_total)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
