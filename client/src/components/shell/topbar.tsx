"use client";

import { Menu, Search } from "lucide-react";

import { Kbd } from "@/components/ui/button";
import { useUI } from "@/lib/store/ui";

/** Top bar: mobile menu toggle, command-palette search, shortcuts hint. */
export function Topbar() {
  const setPaletteOpen = useUI((s) => s.setPaletteOpen);
  const setSidebarOpen = useUI((s) => s.setSidebarOpen);

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-surface px-4 sm:px-6">
      <button
        type="button"
        onClick={() => setSidebarOpen(true)}
        className="rounded-lg p-1.5 text-muted hover:bg-surface-muted md:hidden"
        aria-label="Open menu"
      >
        <Menu className="size-5" />
      </button>

      <button
        type="button"
        onClick={() => setPaletteOpen(true)}
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

      <span className="ml-auto hidden text-sm text-muted-2 sm:block">
        Shortcuts ?
      </span>
    </header>
  );
}
