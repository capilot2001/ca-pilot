"use client";

/**
 * The session's invoice batch — the stateless workspace. Invoices come from a
 * PDF upload or manual entry and live only in the browser for this session.
 *
 * Invoice data is mirrored to sessionStorage so a refresh mid-review doesn't
 * lose work; the source `File` objects are NOT persisted (they can't be
 * serialized), so after a refresh the document viewer simply has nothing to
 * show while the reading is still editable.
 */
import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

import type { Invoice } from "@/lib/api";

export interface BatchItem {
  id: string;
  invoice: Invoice;
  dirty: boolean;
  /** Source file (in-memory only; absent after a refresh or for manual entries). */
  file?: File;
}

interface BatchState {
  items: BatchItem[];
  add: (invoices: Invoice[], files?: File[]) => string[];
  get: (id: string) => BatchItem | undefined;
  updateInvoice: (id: string, invoice: Invoice, dirty?: boolean) => void;
  remove: (id: string) => void;
  clear: () => void;
}

function newId(): string {
  try {
    return crypto.randomUUID();
  } catch {
    return `id-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  }
}

export const useBatch = create<BatchState>()(
  persist(
    (set, get) => ({
      items: [],

      add: (invoices, files) => {
        const created = invoices.map((invoice) => ({
          id: newId(),
          invoice,
          dirty: false,
          // a file can hold several bills; match each invoice back to its file
          file: files?.find((f) => invoice.source_file.startsWith(f.name)),
        }));
        set((s) => ({ items: [...s.items, ...created] }));
        return created.map((c) => c.id);
      },

      get: (id) => get().items.find((i) => i.id === id),

      updateInvoice: (id, invoice, dirty = true) =>
        set((s) => ({
          items: s.items.map((i) =>
            i.id === id ? { ...i, invoice, dirty } : i
          ),
        })),

      remove: (id) =>
        set((s) => ({ items: s.items.filter((i) => i.id !== id) })),

      clear: () => set({ items: [] }),
    }),
    {
      name: "lf_batch",
      storage: createJSONStorage(() => sessionStorage),
      // persist only serializable invoice data — never the File objects
      partialize: (s) => ({
        items: s.items.map(({ id, invoice, dirty }) => ({
          id,
          invoice,
          dirty,
        })),
      }),
    }
  )
);
