"use client";

import { usePathname } from "next/navigation";

export function EvidenceBanner() {
  const pathname = usePathname();
  if (pathname === "/") return null;
  
  // Update to architectural visual language
  return (
    <div className="w-full border-b border-[var(--border)] bg-[var(--background)] px-4 py-3 text-center font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-[var(--foreground)]">
      Evidence-aware research system <span className="mx-2 text-[var(--accent)]">◆</span> synthetic, replay, and production signals remain explicitly separated
    </div>
  );
}
