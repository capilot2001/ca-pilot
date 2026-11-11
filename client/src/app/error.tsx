"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // developers see the real error; the user sees a generic message
    console.error("[route error]", error);
  }, [error]);

  return (
    <div className="grid min-h-[60vh] place-items-center px-4 text-center">
      <div className="space-y-3">
        <p className="text-lg font-semibold">Something went wrong</p>
        <p className="text-sm text-muted">
          An unexpected error occurred. You can try again.
        </p>
        <Button onClick={reset}>Try again</Button>
      </div>
    </div>
  );
}
