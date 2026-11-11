"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { FileText, Plus, Upload } from "lucide-react";

import { ExportMenu } from "@/components/invoices/export-menu";
import { InvoiceTable } from "@/components/invoices/invoice-table";
import { buttonClasses, Kbd } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useBatch } from "@/lib/store/batch";

export default function InvoicesPage() {
  const items = useBatch((s) => s.items);
  const clear = useBatch((s) => s.clear);
  const [mounted, setMounted] = useState(false);
  const [q, setQ] = useState("");

  // avoid a hydration flash: the batch rehydrates from sessionStorage on mount
  useEffect(() => setMounted(true), []);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return items;
    return items.filter(
      (i) =>
        i.invoice.invoice_number.toLowerCase().includes(needle) ||
        i.invoice.party_name.toLowerCase().includes(needle) ||
        i.invoice.source_file.toLowerCase().includes(needle)
    );
  }, [items, q]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">Invoices</h1>
          {mounted && items.length > 0 && (
            <span className="rounded-full bg-surface-muted px-2.5 py-0.5 text-xs font-medium text-muted">
              {items.length} this session
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {mounted && items.length > 0 && (
            <ExportMenu invoices={items.map((i) => i.invoice)} />
          )}
          <Link href="/invoices/new" className={buttonClasses("primary")}>
            <Plus className="size-4" /> New invoice
            <Kbd tone="onBrand">s</Kbd>
          </Link>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-surface">
        <div className="flex items-center gap-3 border-b border-border p-4">
          <Input
            placeholder="Search by number or party"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            disabled={!mounted || items.length === 0}
          />
          {mounted && items.length > 0 && (
            <button
              onClick={clear}
              className="shrink-0 text-sm text-muted hover:text-danger-fg"
            >
              Clear session
            </button>
          )}
        </div>

        {!mounted ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <EmptyState />
        ) : filtered.length === 0 ? (
          <p className="px-6 py-16 text-center text-sm text-muted">
            No invoices match “{q}”.
          </p>
        ) : (
          <InvoiceTable items={filtered} />
        )}
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 px-6 py-20 text-center">
      <span className="grid size-12 place-items-center rounded-full bg-brand-subtle text-brand">
        <FileText className="size-6" />
      </span>
      <div className="space-y-1">
        <p className="text-sm font-medium text-fg">No invoices yet</p>
        <p className="max-w-sm text-sm text-muted">
          Upload a PDF to read it automatically, or enter one by hand. Invoices
          live in this session only — nothing is saved between visits.
        </p>
      </div>
      <Link href="/invoices/new" className={buttonClasses("primary")}>
        <Upload className="size-4" /> Upload or create an invoice
      </Link>
    </div>
  );
}
