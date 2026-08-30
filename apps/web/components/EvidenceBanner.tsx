"use client";

import { usePathname } from "next/navigation";

export function EvidenceBanner() {
  const pathname = usePathname();
  if (pathname === "/") return null;
  return (
    <div className="mt-12 border-b border-[#b7ffe5]/10 bg-[#07110f] px-4 py-2 text-center font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-[#b7ffe5]/65">
      Evidence-aware research system <span className="mx-2 text-[#7cf7d4]">◆</span> synthetic, replay, and production signals remain explicitly separated
    </div>
  );
}
