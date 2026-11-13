import type { Invoice } from "@/lib/api";
import { cn, formatInr } from "@/lib/utils";

function Line({
  label,
  value,
  strong,
}: {
  label: string;
  value: string;
  strong?: boolean;
}) {
  return (
    <div
      className={cn(
        "flex items-center justify-between py-1.5",
        strong && "text-base font-semibold"
      )}
    >
      <span className={cn(strong ? "text-fg" : "text-muted")}>{label}</span>
      <span className={cn("tabular", strong ? "text-fg" : "text-fg")}>
        {value}
      </span>
    </div>
  );
}

export function TaxSummary({ invoice }: { invoice: Invoice }) {
  const t = invoice.tax;
  return (
    <div className="rounded-xl border border-border bg-surface p-4 text-sm">
      <Line label="Taxable value" value={formatInr(invoice.taxable_total)} />
      {t.cgst > 0 && <Line label="CGST" value={formatInr(t.cgst)} />}
      {t.sgst > 0 && <Line label="SGST" value={formatInr(t.sgst)} />}
      {t.igst > 0 && <Line label="IGST" value={formatInr(t.igst)} />}
      {t.cess > 0 && <Line label="Cess" value={formatInr(t.cess)} />}
      {t.round_off !== 0 && (
        <Line label="Round off" value={formatInr(t.round_off)} />
      )}
      <div className="mt-1 border-t border-border pt-1">
        <Line label="Total" value={formatInr(invoice.invoice_total)} strong />
      </div>
    </div>
  );
}
