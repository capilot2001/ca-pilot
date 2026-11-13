"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  FilePlus2,
  FileText,
  LogOut,
  Scale,
  Search,
  Settings,
  Sparkles,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/lib/auth/auth-context";
import { SAMPLE_INVOICES } from "@/lib/sample-data";
import { useBatch } from "@/lib/store/batch";
import { useUI } from "@/lib/store/ui";
import { cn } from "@/lib/utils";

interface Command {
  id: string;
  label: string;
  icon: typeof FileText;
  run: () => void;
}

export function CommandPalette() {
  const open = useUI((s) => s.paletteOpen);
  const setOpen = useUI((s) => s.setPaletteOpen);
  const router = useRouter();
  const { logout } = useAuth();
  const clearBatch = useBatch((s) => s.clear);
  const addBatch = useBatch((s) => s.add);

  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const commands = useMemo<Command[]>(
    () => [
      {
        id: "invoices",
        label: "Go to Invoices",
        icon: FileText,
        run: () => router.push("/invoices"),
      },
      {
        id: "new",
        label: "New invoice",
        icon: FilePlus2,
        run: () => router.push("/invoices/new"),
      },
      {
        id: "reconcile",
        label: "Go to Reconcile",
        icon: Scale,
        run: () => router.push("/reconcile"),
      },
      {
        id: "settings",
        label: "Go to Settings",
        icon: Settings,
        run: () => router.push("/settings"),
      },
      {
        id: "sample",
        label: "Load sample data (demo)",
        icon: Sparkles,
        run: () => {
          clearBatch();
          addBatch(SAMPLE_INVOICES);
          toast.success(`Loaded ${SAMPLE_INVOICES.length} sample invoices`);
          router.push("/invoices");
        },
      },
      {
        id: "clear",
        label: "Clear this session's invoices",
        icon: Trash2,
        run: () => clearBatch(),
      },
      {
        id: "logout",
        label: "Log out",
        icon: LogOut,
        run: () => logout(),
      },
    ],
    [router, logout, clearBatch, addBatch]
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q
      ? commands.filter((c) => c.label.toLowerCase().includes(q))
      : commands;
  }, [commands, query]);

  // global Ctrl/Cmd+K toggles the palette
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(!useUI.getState().paletteOpen);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setOpen]);

  // reset + focus when opened
  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      const t = setTimeout(() => inputRef.current?.focus(), 0);
      return () => clearTimeout(t);
    }
  }, [open]);

  useEffect(() => setActive(0), [query]);

  if (!open) return null;

  function choose(cmd: Command) {
    setOpen(false);
    cmd.run();
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") setOpen(false);
    else if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const cmd = filtered[active];
      if (cmd) choose(cmd);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/30 p-4 pt-[12vh]"
      onMouseDown={() => setOpen(false)}
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
    >
      <div
        className="w-full max-w-lg overflow-hidden rounded-xl border border-border bg-surface shadow-2xl"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 border-b border-border px-3">
          <Search className="size-4 text-muted-2" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Search or jump to…"
            className="h-12 w-full bg-transparent text-sm text-fg outline-none placeholder:text-muted-2"
          />
        </div>
        <ul className="max-h-80 overflow-y-auto p-1.5">
          {filtered.length === 0 && (
            <li className="px-3 py-6 text-center text-sm text-muted">
              No matching commands.
            </li>
          )}
          {filtered.map((cmd, i) => (
            <li key={cmd.id}>
              <button
                onMouseEnter={() => setActive(i)}
                onClick={() => choose(cmd)}
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm",
                  i === active
                    ? "bg-brand-subtle text-brand-subtle-fg"
                    : "text-fg hover:bg-surface-muted"
                )}
              >
                <cmd.icon className="size-4" />
                {cmd.label}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
