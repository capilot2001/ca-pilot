import Link from "next/link";
import { FileText, Plus, Upload } from "lucide-react";

import { buttonClasses, Kbd } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function InvoicesPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Invoices</h1>
        <Link href="/invoices/new" className={buttonClasses("primary")}>
          <Plus className="size-4" /> New invoice
          <Kbd tone="onBrand">s</Kbd>
        </Link>
      </div>

      <div className="rounded-xl border border-border bg-surface">
        <div className="border-b border-border p-4">
          <Input placeholder="Search by number or party" disabled />
        </div>

        {/* Stateless: nothing is persisted, so the list starts empty each session. */}
        <div className="flex flex-col items-center justify-center gap-4 px-6 py-20 text-center">
          <span className="grid size-12 place-items-center rounded-full bg-brand-subtle text-brand">
            <FileText className="size-6" />
          </span>
          <div className="space-y-1">
            <p className="text-sm font-medium text-fg">No invoices yet</p>
            <p className="max-w-sm text-sm text-muted">
              Upload a PDF to read it automatically, or enter one by hand.
              Invoices live in this session only — nothing is saved between
              visits.
            </p>
          </div>
          <Link href="/invoices/new" className={buttonClasses("primary")}>
            <Upload className="size-4" /> Upload or create an invoice
          </Link>
        </div>
      </div>
    </div>
  );
}
