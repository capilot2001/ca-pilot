"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Receipt } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth/auth-context";

export default function LoginPage() {
  const { login, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("demo@ledgerflow.app");
  const [password, setPassword] = useState("demo");

  useEffect(() => {
    if (!isLoading && isAuthenticated) router.replace("/invoices");
  }, [isLoading, isAuthenticated, router]);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    login(email.trim());
    router.replace("/invoices");
  }

  return (
    <div className="grid min-h-dvh place-items-center bg-surface-muted px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2">
          <span className="grid size-10 place-items-center rounded-xl bg-brand text-brand-fg">
            <Receipt className="size-5" />
          </span>
          <h1 className="text-xl font-semibold tracking-tight">LedgerFlow</h1>
          <p className="text-sm text-muted">Sign in to continue</p>
        </div>

        <form
          onSubmit={onSubmit}
          className="space-y-4 rounded-2xl border border-border bg-surface p-6 shadow-sm"
        >
          <div className="space-y-1.5">
            <label htmlFor="email" className="text-sm font-medium">
              Email
            </label>
            <Input
              id="email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1.5">
            <label htmlFor="password" className="text-sm font-medium">
              Password
            </label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <Button type="submit" className="w-full">
            Sign in
          </Button>
          <p className="text-center text-xs text-muted-2">
            Demo sign-in — no account needed yet.
          </p>
        </form>
      </div>
    </div>
  );
}
