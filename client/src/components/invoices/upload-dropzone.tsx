"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { Loader2, UploadCloud } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { useExtract } from "@/lib/invoice-mutations";
import { cn } from "@/lib/utils";

const ACCEPT = ".pdf,.png,.jpg,.jpeg,.webp,.tif,.tiff";

export function UploadDropzone() {
  const router = useRouter();
  const extract = useExtract();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [count, setCount] = useState(0);

  function handleFiles(list: FileList | null) {
    if (!list || list.length === 0) return;
    const files = Array.from(list);
    setCount(files.length);
    extract.mutate(files, {
      onSuccess: () => router.push("/invoices"),
    });
  }

  if (extract.isPending) {
    return (
      <div className="rounded-xl border border-border bg-surface p-6">
        <div className="mb-5 flex items-center gap-2 text-sm font-medium text-fg">
          <Loader2 className="size-4 animate-spin text-brand" />
          Reading {count} file{count === 1 ? "" : "s"}…
        </div>
        <div className="space-y-3">
          {Array.from({ length: Math.min(count, 4) || 1 }).map((_, i) => (
            <div
              key={i}
              className="flex items-center gap-3 rounded-lg border border-border p-3"
            >
              <Skeleton className="size-9 rounded-md" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-3.5 w-1/3" />
                <Skeleton className="h-3 w-1/2" />
              </div>
              <Skeleton className="h-5 w-16 rounded-full" />
            </div>
          ))}
        </div>
        <p className="mt-4 text-xs text-muted">
          Running OCR and reading the page — this can take a few seconds per
          invoice.
        </p>
      </div>
    );
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => inputRef.current?.click()}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
      }}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        handleFiles(e.dataTransfer.files);
      }}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed border-border bg-surface px-6 py-16 text-center transition-colors",
        "hover:border-brand/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        dragging && "border-brand bg-brand-subtle"
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        multiple
        hidden
        onChange={(e) => handleFiles(e.target.files)}
      />
      <span className="grid size-12 place-items-center rounded-full bg-brand-subtle text-brand">
        <UploadCloud className="size-6" />
      </span>
      <div className="space-y-1">
        <p className="text-sm font-medium text-fg">
          Drag &amp; drop invoices, or click to browse
        </p>
        <p className="text-sm text-muted">
          PDF or image — a single file can hold several bills.
        </p>
      </div>
    </div>
  );
}
