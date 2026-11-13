"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { LineItemsEditor } from "@/components/invoices/line-items-editor";
import { Button, Kbd } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import * as api from "@/lib/api";
import type { Invoice, LineItem } from "@/lib/api";
import { useActiveConfig } from "@/lib/queries";
import { STATE_CODES, STATE_OPTIONS } from "@/lib/states";
import { useBatch } from "@/lib/store/batch";
import { cn, formatDisplayDate, formatInr, todayIso } from "@/lib/utils";

const round2 = (n: number) => Math.round(n * 100) / 100;

const BLANK_LINE: LineItem = {
  description: "",
  hsn_sac: "",
  quantity: null,
  unit: "Nos",
  rate: null,
  disc_pct: null,
  taxable_value: null,
  gst_rate: 18,
  amount: null,
  ledger: "",
};

function lineTaxable(it: LineItem): number {
  if (it.taxable_value != null) return it.taxable_value;
  if (it.quantity != null && it.rate != null)
    return round2(it.quantity * it.rate * (1 - (it.disc_pct ?? 0) / 100));
  return 0;
}

export function ManualInvoiceForm() {
  const router = useRouter();
  const add = useBatch((s) => s.add);
  const { data: company } = useActiveConfig();

  const [direction, setDirection] = useState<"sale" | "purchase">("sale");
  const [partyName, setPartyName] = useState("");
  const [partyGstin, setPartyGstin] = useState("");
  const [posCode, setPosCode] = useState("");
  const [number, setNumber] = useState("");
  const [date, setDate] = useState(todayIso());
  const [items, setItems] = useState<LineItem[]>([{ ...BLANK_LINE }]);
  const [notes, setNotes] = useState("");

  const intra = !!company && posCode !== "" && posCode === company.state_code;

  const preview = useMemo(() => {
    let taxable = 0;
    let tax = 0;
    for (const it of items) {
      const lt = lineTaxable(it);
      taxable += lt;
      tax += (lt * (it.gst_rate ?? 0)) / 100;
    }
    taxable = round2(taxable);
    tax = round2(tax);
    const cgst = intra ? round2(tax / 2) : 0;
    const sgst = intra ? round2(tax / 2) : 0;
    const igst = intra ? 0 : tax;
    const pre = taxable + cgst + sgst + igst;
    const total = Math.round(pre);
    return { taxable, cgst, sgst, igst, roundOff: round2(total - pre), total };
  }, [items, intra]);

  const create = useMutation({
    mutationFn: (draft: Invoice) => api.recompute([draft]),
    onSuccess: (result) => {
      const classified = result[0];
      if (!classified) return;
      const [id] = add([classified]);
      toast.success("Invoice created");
      router.push(`/invoices/${id}`);
    },
  });

  function buildDraft(): Invoice {
    return {
      source_file: "",
      ocr_engine: "manual",
      raw_text: "",
      source: "invoice",
      direction,
      nature_of_transaction: "unknown",
      accounting_classification: "",
      entry_mode: "item",
      party_name: partyName.trim(),
      party_gstin: partyGstin.trim().toUpperCase(),
      party_state_code: "",
      party_state: "",
      party_address: "",
      party_pincode: "",
      party_registration_type: "Regular",
      invoice_number: number.trim(),
      invoice_date: date,
      invoice_date_display: formatDisplayDate(date),
      place_of_supply: STATE_CODES[posCode] ?? "",
      place_of_supply_code: posCode,
      items: items
        .filter((it) => lineTaxable(it) > 0 || it.description.trim())
        .map((it) => {
          const t = it.taxable_value ?? lineTaxable(it);
          return { ...it, taxable_value: t, amount: t };
        }),
      taxable_total: 0,
      tax: { cgst: 0, sgst: 0, igst: 0, cess: 0, round_off: 0 },
      printed_tax: null,
      invoice_total: 0,
      dominant_gst_rate: null,
      journal: [],
      itc_eligible: null,
      itc_remarks: notes.trim(),
      assumptions: [],
      exceptions: [],
    };
  }

  function save() {
    if (items.every((it) => lineTaxable(it) <= 0 && !it.description.trim())) {
      toast.error("Add at least one line item.");
      return;
    }
    if (!posCode) {
      toast.error("Choose a place of supply.");
      return;
    }
    create.mutate(buildDraft());
  }

  // Ctrl/Cmd+S saves
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        save();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <div className="space-y-5">
      {/* header details */}
      <section className="space-y-4 rounded-xl border border-border bg-surface p-5">
        <div className="inline-flex rounded-lg border border-border p-0.5 text-sm">
          {(["sale", "purchase"] as const).map((d) => (
            <button
              key={d}
              onClick={() => setDirection(d)}
              className={cn(
                "rounded-md px-3 py-1.5 font-medium capitalize transition-colors",
                direction === d
                  ? "bg-brand text-brand-fg"
                  : "text-muted hover:text-fg"
              )}
            >
              {d}
            </button>
          ))}
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <label className="block space-y-1 sm:col-span-2">
            <span className="text-xs font-medium text-muted">
              {direction === "sale" ? "Customer" : "Supplier"}
            </span>
            <Input
              value={partyName}
              placeholder="Party name"
              onChange={(e) => setPartyName(e.target.value)}
            />
          </label>
          <label className="block space-y-1 sm:col-span-2">
            <span className="text-xs font-medium text-muted">Party GSTIN</span>
            <Input
              value={partyGstin}
              placeholder="Optional"
              onChange={(e) => setPartyGstin(e.target.value.toUpperCase())}
            />
          </label>
          <label className="block space-y-1 sm:col-span-2">
            <span className="text-xs font-medium text-muted">
              Place of supply
            </span>
            <select
              value={posCode}
              onChange={(e) => setPosCode(e.target.value)}
              className="h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <option value="">Choose a state</option>
              {STATE_OPTIONS.map((s) => (
                <option key={s.code} value={s.code}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block space-y-1">
            <span className="text-xs font-medium text-muted">Number</span>
            <Input
              value={number}
              placeholder="Optional"
              onChange={(e) => setNumber(e.target.value)}
            />
          </label>
          <label className="block space-y-1">
            <span className="text-xs font-medium text-muted">Date</span>
            <Input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </label>
        </div>
      </section>

      {/* line items */}
      <section className="space-y-2">
        <h2 className="text-sm font-medium text-muted">Line items</h2>
        <LineItemsEditor items={items} onChange={setItems} />
      </section>

      <div className="grid gap-5 lg:grid-cols-2">
        <label className="block space-y-1">
          <span className="text-xs font-medium text-muted">
            Notes (printed on the document)
          </span>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={4}
            className="w-full rounded-lg border border-border bg-surface p-3 text-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </label>

        {/* live estimate — authoritative figures appear after saving */}
        <div className="rounded-xl border border-border bg-surface p-4 text-sm">
          <Row label="Taxable value" value={formatInr(preview.taxable)} />
          {intra ? (
            <>
              <Row label="CGST" value={formatInr(preview.cgst)} />
              <Row label="SGST" value={formatInr(preview.sgst)} />
            </>
          ) : (
            <Row
              label="IGST"
              value={posCode ? formatInr(preview.igst) : "—"}
            />
          )}
          {preview.roundOff !== 0 && (
            <Row label="Round off" value={formatInr(preview.roundOff)} />
          )}
          <div className="mt-1 border-t border-border pt-1">
            <Row label="Total" value={formatInr(preview.total)} strong />
          </div>
          <p className="mt-2 text-xs text-muted-2">
            Estimate — final GST and the journal are computed on save.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Button onClick={save} disabled={create.isPending}>
          {create.isPending ? "Saving…" : "Save invoice"}
          <Kbd tone="onBrand">⌘S</Kbd>
        </Button>
      </div>
    </div>
  );
}

function Row({
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
      <span className={strong ? "text-fg" : "text-muted"}>{label}</span>
      <span className="tabular text-fg">{value}</span>
    </div>
  );
}
