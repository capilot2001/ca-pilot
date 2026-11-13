"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { useActiveConfig } from "@/lib/queries";

function Row({ label, value }: { label: string; value?: string }) {
  return (
    <div className="flex items-center justify-between border-b border-border py-3 last:border-0">
      <span className="text-sm text-muted">{label}</span>
      <span className="text-sm font-medium text-fg">{value || "—"}</span>
    </div>
  );
}

export default function SettingsPage() {
  const { data, isLoading, isError } = useActiveConfig();

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted">
          The active company. Invoices are classified against its GSTIN.
        </p>
      </div>

      <div className="rounded-xl border border-border bg-surface px-5 py-2">
        {isLoading ? (
          <div className="space-y-3 py-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-5 w-full" />
            ))}
          </div>
        ) : isError || !data ? (
          <p className="py-6 text-sm text-muted">Couldn&apos;t load the company.</p>
        ) : (
          <>
            <Row label="Name" value={data.name} />
            <Row label="GSTIN" value={data.gstin} />
            <Row label="State" value={data.state} />
            <Row label="PAN" value={data.pan} />
            <Row label="Registration" value={data.registration_type} />
            <Row label="Address" value={data.address} />
            <Row label="PIN code" value={data.pincode} />
          </>
        )}
      </div>
    </div>
  );
}
