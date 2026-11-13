"use client";

import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { useState } from "react";
import { Toaster, toast } from "sonner";

import { ApiError } from "@/lib/api";
import { AuthProvider } from "@/lib/auth/auth-context";

/** Any query/mutation error is already a sanitized ApiError — toast its message. */
function toastError(error: unknown) {
  const message =
    error instanceof ApiError
      ? error.message
      : "Something went wrong. Please try again.";
  toast.error(message);
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        queryCache: new QueryCache({ onError: toastError }),
        mutationCache: new MutationCache({ onError: toastError }),
        defaultOptions: {
          queries: {
            retry: 1,
            refetchOnWindowFocus: false,
            staleTime: 30_000,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={client}>
      <AuthProvider>{children}</AuthProvider>
      <Toaster
        position="top-right"
        richColors
        toastOptions={{ className: "font-sans" }}
      />
    </QueryClientProvider>
  );
}
