"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FileText, LogOut, Plus, Receipt, Scale, Settings } from "lucide-react";

import { buttonClasses, Kbd } from "@/components/ui/button";
import { CompanySwitcher } from "@/components/shell/company-switcher";
import { useAuth } from "@/lib/auth/auth-context";
import { useUI } from "@/lib/store/ui";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/invoices", label: "Invoices", icon: FileText },
  { href: "/reconcile", label: "Reconcile", icon: Scale },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const sidebarOpen = useUI((s) => s.sidebarOpen);
  const close = () => useUI.getState().setSidebarOpen(false);

  return (
    <>
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/30 md:hidden"
          onClick={close}
          aria-hidden
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex h-full w-64 shrink-0 flex-col border-r border-border bg-surface transition-transform",
          "md:static md:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* brand */}
        <div className="flex items-center gap-2 px-5 py-4">
          <span className="grid size-8 place-items-center rounded-lg bg-brand text-brand-fg">
            <Receipt className="size-4" />
          </span>
          <span className="text-[15px] font-semibold tracking-tight">
            LedgerFlow
          </span>
        </div>

        {/* company + new invoice */}
        <div className="space-y-3 px-4 pb-2">
          <div>
            <p className="mb-1.5 px-1 text-[11px] font-medium uppercase tracking-wide text-muted-2">
              Company
            </p>
            <CompanySwitcher />
          </div>
          <Link
            href="/invoices/new"
            onClick={close}
            className={buttonClasses("primary", "md", "w-full")}
          >
            <Plus className="size-4" /> New invoice
            <Kbd tone="onBrand">s</Kbd>
          </Link>
        </div>

        {/* nav */}
        <nav className="mt-2 flex-1 space-y-0.5 px-3">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || pathname.startsWith(`${href}/`);
            return (
              <Link
                key={href}
                href={href}
                onClick={close}
                className={cn(
                  "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-brand-subtle text-brand-subtle-fg"
                    : "text-muted hover:bg-surface-muted hover:text-fg"
                )}
              >
                <Icon className="size-4" />
                {label}
              </Link>
            );
          })}
        </nav>

        {/* footer */}
        <div className="space-y-0.5 border-t border-border px-3 py-3">
          <Link
            href="/settings"
            onClick={close}
            className={cn(
              "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              pathname === "/settings"
                ? "bg-brand-subtle text-brand-subtle-fg"
                : "text-muted hover:bg-surface-muted hover:text-fg"
            )}
          >
            <Settings className="size-4" />
            Settings
          </Link>
          <div className="mt-2 flex items-center justify-between px-3 py-1.5">
            <span className="truncate text-sm text-muted">
              {user?.name ?? "Demo Owner"}
            </span>
            <button
              onClick={logout}
              className="flex items-center gap-1 text-xs text-muted hover:text-danger-fg"
            >
              <LogOut className="size-3.5" /> Log out
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
