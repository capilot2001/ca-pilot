"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, Download, Loader2 } from "lucide-react";

import { buttonClasses } from "@/components/ui/button";
import { reviewStatus } from "@/components/ui/status-pill";
import type { ExportKind, Invoice } from "@/lib/api";
import { useExport } from "@/lib/invoice-mutations";
import { cn } from "@/lib/utils";

const GROUPS: { label: string; items: { kind: ExportKind; label: string }[] }[] =
  [
    {
      label: "Tally masters & vouchers",
      items: [
        { kind: "masters-xlsx", label: "Masters — Excel" },
        { kind: "vouchers-xlsx", label: "Vouchers — Excel" },
        { kind: "masters-xml", label: "Masters — XML" },
        { kind: "vouchers-xml", label: "Vouchers — XML" },
      ],
    },
    {
      label: "Reconciliation",
      items: [
        { kind: "recon-xlsx", label: "Reconciliation — Excel" },
        { kind: "recon-pdf", label: "Reconciliation — PDF" },
      ],
    },
  ];

export function ExportMenu({ invoices }: { invoices: Invoice[] }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const exporter = useExport();

  const errorCount = invoices.filter(
    (i) => reviewStatus(i.exceptions) === "error"
  ).length;

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  function run(kind: ExportKind) {
    setOpen(false);
    exporter.mutate({ kind, invoices });
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        disabled={invoices.length === 0 || exporter.isPending}
        className={buttonClasses("outline", "md")}
      >
        {exporter.isPending ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <Download className="size-4" />
        )}
        Export
        <ChevronDown className="size-4 text-muted" />
      </button>

      {open && (
        <div className="absolute right-0 z-20 mt-2 w-64 overflow-hidden rounded-xl border border-border bg-surface shadow-lg">
          {errorCount > 0 && (
            <p className="border-b border-border bg-warning-bg px-3 py-2 text-xs text-warning-fg">
              {errorCount} invoice{errorCount === 1 ? "" : "s"} with errors
              {errorCount === 1 ? " is" : " are"} left out of the vouchers until
              fixed.
            </p>
          )}
          {GROUPS.map((group) => (
            <div key={group.label} className="py-1">
              <p className="px-3 py-1 text-[11px] font-medium uppercase tracking-wide text-muted-2">
                {group.label}
              </p>
              {group.items.map((item) => (
                <button
                  key={item.kind}
                  onClick={() => run(item.kind)}
                  className={cn(
                    "block w-full px-3 py-2 text-left text-sm text-fg hover:bg-surface-muted"
                  )}
                >
                  {item.label}
                </button>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
