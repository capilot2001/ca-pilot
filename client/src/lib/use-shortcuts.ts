"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useUI } from "@/lib/store/ui";

function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el) return false;
  const tag = el.tagName;
  return (
    tag === "INPUT" ||
    tag === "TEXTAREA" ||
    tag === "SELECT" ||
    el.isContentEditable
  );
}

/** Single-key navigation shortcuts: s = new invoice, r = invoices. */
export function useGlobalShortcuts() {
  const router = useRouter();
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (useUI.getState().paletteOpen) return;
      if (isTyping(e.target)) return;
      const k = e.key.toLowerCase();
      if (k === "s") {
        e.preventDefault();
        router.push("/invoices/new");
      } else if (k === "r") {
        e.preventDefault();
        router.push("/invoices");
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [router]);
}
