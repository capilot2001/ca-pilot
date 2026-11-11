import Link from "next/link";
import { ArrowLeft, PencilLine, Upload } from "lucide-react";

export default function NewInvoicePage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="space-y-1">
        <Link
          href="/invoices"
          className="inline-flex items-center gap-1 text-sm text-muted hover:text-fg"
        >
          <ArrowLeft className="size-4" /> Invoices
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">New invoice</h1>
        <p className="text-sm text-muted">
          Read an invoice from a PDF, or enter the details yourself.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {/* Upload — wired in P2 */}
        <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-5">
          <span className="grid size-10 place-items-center rounded-lg bg-brand-subtle text-brand">
            <Upload className="size-5" />
          </span>
          <div className="space-y-1">
            <p className="font-medium">Upload a PDF</p>
            <p className="text-sm text-muted">
              We read the party, line items and tax, then you review and correct
              before exporting.
            </p>
          </div>
          <span className="mt-auto text-xs font-medium text-muted-2">
            Coming next
          </span>
        </div>

        {/* Manual — wired in P3 */}
        <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-5">
          <span className="grid size-10 place-items-center rounded-lg bg-brand-subtle text-brand">
            <PencilLine className="size-5" />
          </span>
          <div className="space-y-1">
            <p className="font-medium">Enter manually</p>
            <p className="text-sm text-muted">
              Fill in the customer, line items and GST — the tax total is
              computed for you.
            </p>
          </div>
          <span className="mt-auto text-xs font-medium text-muted-2">
            Coming next
          </span>
        </div>
      </div>
    </div>
  );
}
