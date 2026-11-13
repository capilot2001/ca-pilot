"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, RefreshCw, Sparkles, Upload } from "lucide-react";
import { toast } from "sonner";

import { ExportMenu } from "@/components/invoices/export-menu";
import { ReconTable } from "@/components/reconcile/recon-table";
import { Button, buttonClasses } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { ReconSummary } from "@/lib/api";
import { useImportGstr2a, useReconcile } from "@/lib/invoice-mutations";
import { SAMPLE_INVOICES } from "@/lib/sample-data";
import { useBatch } from "@/lib/store/batch";
import { cn, formatInr } from "@/lib/utils";

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "danger";
}) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-2">
        {label}
      </p>
      <p
        className={cn(
          "tabular mt-1 text-xl font-semibold",
          tone === "danger" ? "text-danger-fg" : "text-fg"
        )}
      >
        {value}
      </p>
    </div>
  );
}

export default function ReconcilePage() {
  const items = useBatch((s) => s.items);
  const add = useBatch((s) => s.add);
  const clear = useBatch((s) => s.clear);
  const loadSample = () => {
    clear();
    add(SAMPLE_INVOICES);
    toast.success(`Loaded ${SAMPLE_INVOICES.length} sample invoices`);
  };
  const invoices = useMemo(() => items.map((i) => i.invoice), [items]);
  const importer = useImportGstr2a();
  const reconcile = useReconcile();
  const inputRef = useRef<HTMLInputElement>(null);

  const [mounted, setMounted] = useState(false);
  const [result, setResult] = useState<ReconSummary | null>(null);
  useEffect(() => setMounted(true), []);

  const count = invoices.length;
  useEffect(() => {
    if (!mounted) return;
    if (count > 0) reconcile.mutate(invoices, { onSuccess: setResult });
    else setResult(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mounted, count]);

  function handleImport(list: FileList | null) {
    if (!list || list.length === 0) return;
    importer.mutate(Array.from(list));
  }

  const busy = importer.isPending || reconcile.isPending;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            GSTR-2A reconciliation
          </h1>
          <p className="text-sm text-muted">
            Compares this session&apos;s purchase invoices with GSTR-2A rows.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            type="file"
            accept=".xlsx,.xls"
            multiple
            hidden
            onChange={(e) => handleImport(e.target.files)}
          />
          <Button
            variant="outline"
            onClick={() => inputRef.current?.click()}
            disabled={importer.isPending}
          >
            {importer.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Upload className="size-4" />
            )}
            Import GSTR-2A
          </Button>
          <Button variant="outline" onClick={loadSample} title="Replace the session with offline demo data">
            <Sparkles className="size-4" /> Load sample
          </Button>
          {mounted && count > 0 && <ExportMenu invoices={invoices} />}
        </div>
      </div>

      {!mounted ? (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>
          <Skeleton className="h-40 w-full" />
        </div>
      ) : count === 0 ? (
        <div className="rounded-xl border border-border bg-surface px-6 py-16 text-center">
          <p className="text-sm font-medium text-fg">Nothing to reconcile yet</p>
          <p className="mx-auto mt-1 max-w-sm text-sm text-muted">
            Add purchase invoices (upload or enter them), then import the GSTR-2A
            workbook to compare.
          </p>
          <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
            <Link href="/invoices/new" className={buttonClasses("primary")}>
              Add invoices
            </Link>
            <button onClick={loadSample} className={buttonClasses("outline")}>
              Load sample data
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <Stat label="Books" value={String(result?.books_count ?? 0)} />
            <Stat label="GSTR-2A" value={String(result?.gstr2a_count ?? 0)} />
            <Stat label="Matched" value={String(result?.matched ?? 0)} />
            <Stat label="Only in 2A" value={String(result?.only_in_2a ?? 0)} />
            <Stat
              label="Only in books"
              value={String(result?.only_in_books ?? 0)}
            />
            <Stat
              label="ITC at risk"
              value={formatInr(result?.itc_at_risk ?? 0)}
              tone="danger"
            />
          </div>

          <div className="flex items-center gap-3">
            <h2 className="text-sm font-medium text-muted">Line by line</h2>
            <button
              onClick={() =>
                reconcile.mutate(invoices, { onSuccess: setResult })
              }
              disabled={busy}
              className="flex items-center gap-1 text-xs text-brand hover:underline disabled:opacity-50"
            >
              <RefreshCw
                className={cn("size-3.5", reconcile.isPending && "animate-spin")}
              />
              Re-run
            </button>
          </div>

          {reconcile.isPending && !result ? (
            <Skeleton className="h-40 w-full" />
          ) : (
            <ReconTable lines={result?.lines ?? []} />
          )}
        </div>
      )}
    </div>
  );
}
