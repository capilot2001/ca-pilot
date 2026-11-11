"use client";

import { Search } from "lucide-react";
import { Kbd } from "@/components/ui/button";

/** Top bar: command-palette search affordance + shortcuts hint.
 *  The palette itself is wired in a later phase; this matches the reference look. */
export function Topbar() {
  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-surface px-6">
      <button
        type="button"
        className="flex h-9 w-full max-w-md items-center gap-2 rounded-lg border border-border bg-surface-muted px-3 text-sm text-muted-2 hover:bg-surface"
        aria-label="Search or jump to"
      >
        <Search className="size-4" />
        <span>Search or jump to…</span>
        <span className="ml-auto flex items-center gap-1">
          <Kbd>Ctrl</Kbd>
          <Kbd>K</Kbd>
        </span>
      </button>
      <span className="ml-auto text-sm text-muted-2">Shortcuts ?</span>
    </header>
  );
}
