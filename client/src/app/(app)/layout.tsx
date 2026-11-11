"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { CommandPalette } from "@/components/shell/command-palette";
import { Sidebar } from "@/components/shell/sidebar";
import { Topbar } from "@/components/shell/topbar";
import { useAuth } from "@/lib/auth/auth-context";
import { useUI } from "@/lib/store/ui";
import { useGlobalShortcuts } from "@/lib/use-shortcuts";

/** Dashboard shell + auth guard. Unauthenticated users are sent to /login. */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  useGlobalShortcuts();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) router.replace("/login");
  }, [isLoading, isAuthenticated, router]);

  // close the mobile drawer whenever the route changes
  useEffect(() => {
    useUI.getState().setSidebarOpen(false);
  }, [pathname]);

  if (isLoading || !isAuthenticated) {
    return (
      <div className="grid h-dvh place-items-center text-sm text-muted">
        Loading…
      </div>
    );
  }

  return (
    <div className="flex h-dvh overflow-hidden">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-6xl px-4 py-6 sm:px-8 sm:py-8">
            {children}
          </div>
        </main>
      </div>
      <CommandPalette />
    </div>
  );
}
