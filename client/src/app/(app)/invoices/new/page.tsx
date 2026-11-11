"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowLeft, PencilLine, Upload } from "lucide-react";

import { UploadDropzone } from "@/components/invoices/upload-dropzone";
import { cn } from "@/lib/utils";

type Mode = "upload" | "manual";

export default function NewInvoicePage() {
  const [mode, setMode] = useState<Mode | null>(null);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="space-y-1">
        <Link
          href="/invoices"
          className="inline-flex items-center gap-1 text-sm text-muted hover:text-fg"
        >
          <ArrowLeft className="size-4" /> Invoices
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">New invoice</h1>
        <p className="text-sm text-muted">
          Read an invoice from a PDF, or enter the details yourself.
        </p>
      </div>

      {mode === null && (
        <div className="grid gap-4 sm:grid-cols-2">
          <ModeCard
            icon={<Upload className="size-5" />}
            title="Upload a PDF"
            body="We read the party, line items and tax, then you review and correct before exporting."
            onClick={() => setMode("upload")}
          />
          <ModeCard
            icon={<PencilLine className="size-5" />}
            title="Enter manually"
            body="Fill in the customer, line items and GST — the tax total is computed for you."
            note="Coming next"
            onClick={() => setMode("manual")}
          />
        </div>
      )}

      {mode === "upload" && (
        <div className="space-y-3">
          <button
            onClick={() => setMode(null)}
            className="inline-flex items-center gap-1 text-sm text-muted hover:text-fg"
          >
            <ArrowLeft className="size-4" /> Choose a different way
          </button>
          <UploadDropzone />
        </div>
      )}

      {mode === "manual" && (
        <div className="space-y-3">
          <button
            onClick={() => setMode(null)}
            className="inline-flex items-center gap-1 text-sm text-muted hover:text-fg"
          >
            <ArrowLeft className="size-4" /> Choose a different way
          </button>
          <div className="rounded-xl border border-border bg-surface px-6 py-12 text-center text-sm text-muted">
            Manual entry is coming next (P3).
          </div>
        </div>
      )}
    </div>
  );
}

function ModeCard({
  icon,
  title,
  body,
  note,
  onClick,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
  note?: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex flex-col gap-3 rounded-xl border border-border bg-surface p-5 text-left transition-colors",
        "hover:border-brand/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      )}
    >
      <span className="grid size-10 place-items-center rounded-lg bg-brand-subtle text-brand">
        {icon}
      </span>
      <div className="space-y-1">
        <p className="font-medium">{title}</p>
        <p className="text-sm text-muted">{body}</p>
      </div>
      {note && (
        <span className="mt-auto text-xs font-medium text-muted-2">{note}</span>
      )}
    </button>
  );
}
