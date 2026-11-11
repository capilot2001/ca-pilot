"use client";

import { ChevronsUpDown } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { useActivateClient, useClients } from "@/lib/queries";
import { cn } from "@/lib/utils";

/** The active-company selector (sidebar). Maps to /api/clients + activate. */
export function CompanySwitcher() {
  const { data, isLoading, isError } = useClients();
  const activate = useActivateClient();

  if (isLoading) return <Skeleton className="h-10 w-full" />;

  if (isError || !data) {
    return (
      <div className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-muted">
        Couldn&apos;t load companies
      </div>
    );
  }

  return (
    <div className="relative">
      <select
        aria-label="Active company"
        value={data.active_id ?? ""}
        disabled={activate.isPending}
        onChange={(e) => activate.mutate(Number(e.target.value))}
        className={cn(
          "h-10 w-full appearance-none rounded-lg border border-border bg-surface pl-3 pr-9 text-sm font-medium text-fg",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-brand",
          "disabled:opacity-60"
        )}
      >
        {data.clients.length === 0 && <option value="">No companies</option>}
        {data.clients.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>
      <ChevronsUpDown className="pointer-events-none absolute right-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-2" />
    </div>
  );
}
