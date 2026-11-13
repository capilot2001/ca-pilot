import Link from "next/link";
import { buttonClasses } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="grid min-h-dvh place-items-center px-4 text-center">
      <div className="space-y-3">
        <p className="text-lg font-semibold">Page not found</p>
        <p className="text-sm text-muted">
          The page you&apos;re looking for doesn&apos;t exist.
        </p>
        <Link href="/invoices" className={buttonClasses("primary")}>
          Back to invoices
        </Link>
      </div>
    </div>
  );
}
