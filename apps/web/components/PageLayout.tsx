"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";

const NAV_SECTIONS = [
  {
    label: "Observability",
    items: [
      { href: "/dashboard", label: "Overview" },
      { href: "/runs", label: "Runs" },
      { href: "/timeline", label: "Timeline" },
    ],
  },
  {
    label: "Diagnostics",
    items: [
      { href: "/graph", label: "Causal Graph" },
      { href: "/rationale", label: "Rationale" },
    ],
  },
  {
    label: "Replay",
    items: [
      { href: "/replay", label: "Replay Lab" },
      { href: "/scheduler", label: "BCRB Scheduler" },
      { href: "/experiments", label: "Experiments" },
    ],
  },
  {
    label: "Governance",
    items: [
      { href: "/policy", label: "Policy Console" },
      { href: "/recovery", label: "Recovery Console" },
      { href: "/ledger", label: "Certificate Ledger" },
    ],
  },
  {
    label: "Advanced",
    items: [
      { href: "/security", label: "Security & Hardening" },
      { href: "/diffusion", label: "Diffusion" },
    ],
  },
];

interface PageLayoutProps {
  title: string;
  subtitle?: string;
  badge?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}

export function PageLayout({ title, subtitle, badge, actions, children }: PageLayoutProps) {
  const pathname = usePathname();

  const currentSection = NAV_SECTIONS.find(s =>
    s.items.some(i => pathname.startsWith(i.href))
  );

  return (
    <div className="min-h-screen bg-[#ECEAE2] flex">
      {/* ── Sidebar ── */}
      <aside className="w-56 border-r border-[#0a0a0a] flex-shrink-0 flex flex-col pt-12 sticky top-0 h-screen overflow-y-auto">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label} className="border-b border-[#0a0a0a]">
            <div className="px-5 py-2.5 font-mono text-[10px] tracking-[0.2em] uppercase text-[#888]">
              {section.label}
            </div>
            {section.items.map((item) => {
              const active = pathname === item.href || pathname.startsWith(item.href + "/");
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`block px-5 py-2.5 font-mono text-xs tracking-wide border-t border-[#0a0a0a]/10 transition-colors
                    ${active
                      ? "bg-[#0a0a0a] text-[#ECEAE2]"
                      : "text-[#0a0a0a] hover:bg-[#0a0a0a]/5"
                    }`}
                >
                  {active && <span className="mr-2 opacity-40">▶</span>}
                  {item.label}
                </Link>
              );
            })}
          </div>
        ))}
      </aside>

      {/* ── Main Content ── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Page header bar */}
        <div className="border-b border-[#0a0a0a] px-8 py-5 flex items-center justify-between">
          <div>
            <h1 className="font-sans font-bold text-2xl tracking-tight text-[#0a0a0a] leading-tight">{title}</h1>
            {subtitle && (
              <p className="font-mono text-xs text-[#888] tracking-wide mt-0.5">{subtitle}</p>
            )}
          </div>
          <div className="flex items-center gap-3">
            {badge}
            {actions}
          </div>
        </div>

        {/* Page body */}
        <div className="flex-1 overflow-y-auto">
          {children}
        </div>
      </div>
    </div>
  );
}
