"use client";

import { useEffect, useState } from "react";
import { FileWarning } from "lucide-react";

/** Show the source bill beside the reading, so the CA can verify against it. */
export function DocumentViewer({
  file,
  sourceName,
}: {
  file?: File;
  sourceName: string;
}) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!file) {
      setUrl(null);
      return;
    }
    const objectUrl = URL.createObjectURL(file);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);

  if (!file || !url) {
    return (
      <div className="flex h-full min-h-80 flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border bg-surface-muted p-6 text-center">
        <FileWarning className="size-6 text-muted-2" />
        <p className="text-sm font-medium text-fg">Source not available</p>
        <p className="max-w-xs text-xs text-muted">
          The original file isn&apos;t kept after a refresh. The reading below is
          still editable — re-upload to see the document again.
        </p>
      </div>
    );
  }

  const isPdf =
    file.type === "application/pdf" ||
    file.name.toLowerCase().endsWith(".pdf");

  if (isPdf) {
    return (
      <iframe
        title={sourceName}
        src={url}
        className="h-full min-h-[32rem] w-full rounded-lg border border-border bg-white"
      />
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element -- blob URL, not a remote asset
    <img
      src={url}
      alt={sourceName}
      className="max-h-[42rem] w-full rounded-lg border border-border bg-white object-contain"
    />
  );
}
