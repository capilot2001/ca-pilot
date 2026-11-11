"use client";

import { Plus, Trash2 } from "lucide-react";

import type { LineItem } from "@/lib/api";
import { cn } from "@/lib/utils";

const GST_RATES = [0, 5, 12, 18, 28];

const EMPTY_LINE: LineItem = {
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

const num = (v: number | null) => (v === null || v === undefined ? "" : String(v));
const toNum = (s: string) => (s.trim() === "" ? null : Number(s));

function Cell(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      // select on focus so typing replaces the value rather than appending
      onFocus={(e) => e.target.select()}
      className={cn(
        "h-9 w-full bg-transparent px-2 text-sm text-fg outline-none",
        "focus:bg-brand-subtle/40",
        props.className
      )}
    />
  );
}

export function LineItemsEditor({
  items,
  onChange,
}: {
  items: LineItem[];
  onChange: (items: LineItem[]) => void;
}) {
  const setItem = (idx: number, patch: Partial<LineItem>) =>
    onChange(items.map((it, i) => (i === idx ? { ...it, ...patch } : it)));
  const addLine = () => onChange([...items, { ...EMPTY_LINE }]);
  const removeLine = (idx: number) =>
    onChange(items.filter((_, i) => i !== idx));

  return (
    <div className="overflow-hidden rounded-xl border border-border">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-sm">
          <thead>
            <tr className="border-b border-border bg-surface-muted text-left text-xs uppercase tracking-wide text-muted-2">
              <th className="px-2 py-2 font-medium">Description</th>
              <th className="px-2 py-2 font-medium">HSN/SAC</th>
              <th className="px-2 py-2 font-medium">Qty</th>
              <th className="px-2 py-2 font-medium">Unit</th>
              <th className="px-2 py-2 font-medium">Rate</th>
              <th className="px-2 py-2 font-medium">Disc %</th>
              <th className="px-2 py-2 font-medium">GST</th>
              <th className="px-2 py-2 font-medium">Taxable</th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody>
            {items.map((it, idx) => (
              <tr key={idx} className="border-b border-border last:border-0">
                <td className="min-w-40">
                  <Cell
                    value={it.description}
                    placeholder="Item"
                    onChange={(e) => setItem(idx, { description: e.target.value })}
                  />
                </td>
                <td className="w-24">
                  <Cell
                    value={it.hsn_sac}
                    onChange={(e) => setItem(idx, { hsn_sac: e.target.value })}
                  />
                </td>
                <td className="w-16">
                  <Cell
                    type="number"
                    value={num(it.quantity)}
                    onChange={(e) =>
                      setItem(idx, { quantity: toNum(e.target.value) })
                    }
                  />
                </td>
                <td className="w-16">
                  <Cell
                    value={it.unit}
                    onChange={(e) => setItem(idx, { unit: e.target.value })}
                  />
                </td>
                <td className="w-20">
                  <Cell
                    type="number"
                    value={num(it.rate)}
                    onChange={(e) => setItem(idx, { rate: toNum(e.target.value) })}
                  />
                </td>
                <td className="w-16">
                  <Cell
                    type="number"
                    value={num(it.disc_pct)}
                    onChange={(e) =>
                      setItem(idx, { disc_pct: toNum(e.target.value) })
                    }
                  />
                </td>
                <td className="w-20">
                  <select
                    value={it.gst_rate ?? 18}
                    onChange={(e) =>
                      setItem(idx, { gst_rate: Number(e.target.value) })
                    }
                    className="h-9 w-full bg-transparent px-2 text-sm text-fg outline-none focus:bg-brand-subtle/40"
                  >
                    {(GST_RATES.includes(it.gst_rate ?? 18)
                      ? GST_RATES
                      : [...GST_RATES, it.gst_rate as number]
                    ).map((r) => (
                      <option key={r} value={r}>
                        {r}%
                      </option>
                    ))}
                  </select>
                </td>
                <td className="w-28">
                  <Cell
                    type="number"
                    value={num(it.taxable_value)}
                    onChange={(e) => {
                      const v = toNum(e.target.value);
                      setItem(idx, { taxable_value: v, amount: v });
                    }}
                  />
                </td>
                <td className="px-1 text-center">
                  <button
                    onClick={() => removeLine(idx)}
                    aria-label="Remove line"
                    className="text-muted-2 hover:text-danger-fg"
                  >
                    <Trash2 className="size-4" />
                  </button>
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr>
                <td colSpan={9} className="px-3 py-6 text-center text-sm text-muted">
                  No line items. Add one below.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <button
        onClick={addLine}
        className="flex w-full items-center gap-1.5 border-t border-border px-3 py-2.5 text-sm font-medium text-brand hover:bg-surface-muted"
      >
        <Plus className="size-4" /> Add line
      </button>
    </div>
  );
}
