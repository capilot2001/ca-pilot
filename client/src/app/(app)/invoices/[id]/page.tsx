"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, RefreshCw, Trash2 } from "lucide-react";

import { DocumentViewer } from "@/components/invoices/document-viewer";
import { ExceptionsPanel } from "@/components/invoices/exceptions-panel";
import { ExportMenu } from "@/components/invoices/export-menu";
import { JournalPreview } from "@/components/invoices/journal-preview";
import { LineItemsEditor } from "@/components/invoices/line-items-editor";
import { TaxSummary } from "@/components/invoices/tax-summary";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { InvoiceStatusPill } from "@/components/ui/status-pill";
import type { Invoice, LineItem } from "@/lib/api";
import { useRecompute } from "@/lib/invoice-mutations";
import { useBatch } from "@/lib/store/batch";

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
function displayDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return "";
  return `${Number(m[3])}-${MONTHS[Number(m[2]) - 1]}-${m[1]}`;
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1">
      <span className="text-xs font-medium text-muted">{label}</span>
      {children}
    </label>
  );
}

export default function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const item = useBatch((s) => s.items.find((i) => i.id === id));
  const updateInvoice = useBatch((s) => s.updateInvoice);
  const remove = useBatch((s) => s.remove);
  const recompute = useRecompute(id);

  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!mounted) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-96 w-full" />
          <div className="space-y-3">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        </div>
      </div>
    );
  }

  if (!item) {
    return (
      <div className="mx-auto max-w-md space-y-3 py-16 text-center">
        <p className="text-lg font-semibold">Invoice not found</p>
        <p className="text-sm text-muted">
          It may have been cleared, or the page was refreshed (invoices aren&apos;t
          saved between sessions).
        </p>
        <Link
          href="/invoices"
          className="inline-flex items-center gap-1 text-sm text-brand hover:underline"
        >
          <ArrowLeft className="size-4" /> Back to invoices
        </Link>
      </div>
    );
  }

  const inv = item.invoice;
  const patch = (p: Partial<Invoice>) =>
    updateInvoice(id, { ...inv, ...p }, true);
  const setItems = (items: LineItem[]) => patch({ items });

  return (
    <div className="space-y-6">
      {/* header */}
      <div className="space-y-3">
        <Link
          href="/invoices"
          className="inline-flex items-center gap-1 text-sm text-muted hover:text-fg"
        >
          <ArrowLeft className="size-4" /> Invoices
        </Link>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold tracking-tight">
              {inv.invoice_number || inv.source_file}
            </h1>
            <InvoiceStatusPill invoice={inv} />
            {item.dirty && (
              <span className="text-xs font-medium text-warning-fg">
                edited — recompute to update tax
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <ExportMenu invoices={[inv]} />
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                remove(id);
                router.push("/invoices");
              }}
            >
              <Trash2 className="size-4" /> Remove
            </Button>
            <Button
              size="sm"
              disabled={recompute.isPending}
              onClick={() => recompute.mutate(inv)}
            >
              <RefreshCw
                className={recompute.isPending ? "size-4 animate-spin" : "size-4"}
              />
              Recompute
            </Button>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* source document */}
        <div className="lg:sticky lg:top-6 lg:self-start">
          <DocumentViewer file={item.file} sourceName={inv.source_file} />
        </div>

        {/* the reading */}
        <div className="space-y-5">
          <ExceptionsPanel invoice={inv} />

          <section className="space-y-3 rounded-xl border border-border bg-surface p-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Party">
                <Input
                  value={inv.party_name}
                  onChange={(e) => patch({ party_name: e.target.value })}
                />
              </Field>
              <Field label="Party GSTIN">
                <Input
                  value={inv.party_gstin}
                  onChange={(e) =>
                    patch({ party_gstin: e.target.value.toUpperCase() })
                  }
                />
              </Field>
              <Field label="Direction">
                <select
                  value={inv.direction}
                  onChange={(e) =>
                    patch({ direction: e.target.value as Invoice["direction"] })
                  }
                  className="h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <option value="purchase">Purchase</option>
                  <option value="sale">Sale</option>
                  <option value="unknown">Unknown</option>
                </select>
              </Field>
              <Field label="Place of supply">
                <Input
                  value={inv.place_of_supply}
                  onChange={(e) => patch({ place_of_supply: e.target.value })}
                />
              </Field>
              <Field label="Invoice number">
                <Input
                  value={inv.invoice_number}
                  onChange={(e) => patch({ invoice_number: e.target.value })}
                />
              </Field>
              <Field label="Invoice date">
                <Input
                  type="date"
                  value={inv.invoice_date}
                  onChange={(e) =>
                    patch({
                      invoice_date: e.target.value,
                      invoice_date_display: displayDate(e.target.value),
                    })
                  }
                />
              </Field>
            </div>
          </section>

          <section className="space-y-2">
            <h2 className="text-sm font-medium text-muted">Line items</h2>
            <LineItemsEditor items={inv.items} onChange={setItems} />
          </section>

          <TaxSummary invoice={inv} />

          <section className="space-y-2">
            <h2 className="text-sm font-medium text-muted">Journal entry</h2>
            <JournalPreview invoice={inv} />
          </section>
        </div>
      </div>
    </div>
  );
}
