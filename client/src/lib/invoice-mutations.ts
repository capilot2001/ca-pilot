"use client";

import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";

import * as api from "@/lib/api";
import type { ExportKind, Invoice } from "@/lib/api";
import { reviewStatus } from "@/components/ui/status-pill";
import { useBatch } from "@/lib/store/batch";

/** Upload files → extract → add the readings to the session batch. */
export function useExtract() {
  const add = useBatch((s) => s.add);
  return useMutation({
    mutationFn: (files: File[]) => api.extract(files),
    onSuccess: (invoices, files) => {
      add(invoices, files);
      const errors = invoices.filter(
        (i) => reviewStatus(i.exceptions) === "error"
      ).length;
      if (errors) {
        toast.warning(
          `${invoices.length} read, ${errors} need${errors === 1 ? "s" : ""} attention`
        );
      } else {
        toast.success(
          `${invoices.length} invoice${invoices.length === 1 ? "" : "s"} read`
        );
      }
    },
  });
}

/** Download a Tally export for the current batch. */
export function useExport() {
  return useMutation({
    mutationFn: ({
      kind,
      invoices,
    }: {
      kind: ExportKind;
      invoices: Invoice[];
    }) => api.downloadExport(kind, invoices),
    onSuccess: () => toast.success("Download started"),
  });
}

/** Re-derive tax, journal, classification and exceptions after an edit. */
export function useRecompute(id: string) {
  const updateInvoice = useBatch((s) => s.updateInvoice);
  return useMutation({
    mutationFn: (invoice: Invoice) => api.recompute([invoice]),
    onSuccess: (result) => {
      const recomputed = result[0];
      if (recomputed) {
        updateInvoice(id, recomputed, false);
        toast.success("Recomputed");
      }
    },
  });
}
