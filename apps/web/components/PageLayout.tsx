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
    <div className="console-surface console-grid min-h-screen flex text-[#eafff7]">
      {/* ── Sidebar ── */}
      <aside className="hidden lg:flex w-64 border-r border-[#b7ffe5]/10 flex-shrink-0 flex-col pt-10 sticky top-0 h-screen overflow-y-auto bg-[#06100e]/70 backdrop-blur-xl">
        <div className="px-5 pb-5 border-b border-[#b7ffe5]/10">
          <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[.18em] text-[#7cf7d4]">
            <span className="signal-dot h-1.5 w-1.5 rounded-full bg-[#7cf7d4]" /> Control plane online
          </div>
          <div className="mt-3 text-sm font-semibold text-[#eafff7]">Causal Operations</div>
          <div className="mt-1 font-mono text-[10px] text-[#8eb1a5]">Tenant-scoped reliability cockpit</div>
        </div>
        {NAV_SECTIONS.map((section) => (
          <div key={section.label} className="border-b border-[#b7ffe5]/10 py-2">
            <div className="px-5 py-2.5 font-mono text-[9px] tracking-[0.22em] uppercase text-[#628378]">
              {section.label}
            </div>
            {section.items.map((item) => {
              const active = pathname === item.href || pathname.startsWith(item.href + "/");
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`mx-2 flex items-center rounded-lg px-3 py-2.5 font-mono text-[11px] tracking-wide transition-all
                    ${active
                      ? "bg-[#7cf7d4] text-[#07110f] shadow-[0_0_32px_rgba(124,247,212,.13)]"
                      : "text-[#9ab9af] hover:bg-[#b7ffe5]/5 hover:text-[#eafff7]"
                    }`}
                >
                  <span className={`mr-2 h-1.5 w-1.5 rounded-full ${active ? 'bg-[#07110f]' : 'bg-[#39574e]'}`} />
                  {item.label}
                </Link>
              );
            })}
          </div>
        ))}
      </aside>

      {/* ── Main Content ── */}
      <div className="min-w-0 flex-1 flex flex-col overflow-hidden">
        <nav aria-label="Console sections" className="lg:hidden flex gap-2 overflow-x-auto border-b border-[#b7ffe5]/10 bg-[#06100e]/80 px-4 py-3 [scrollbar-width:none]">
          {NAV_SECTIONS.flatMap(section => section.items).map(item => {
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`shrink-0 rounded-full border px-3 py-1.5 font-mono text-[9px] uppercase tracking-wider ${active ? 'border-[#7cf7d4]/30 bg-[#7cf7d4] text-[#07110f]' : 'border-[#b7ffe5]/10 text-[#8eb1a5]'}`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        {/* Page header bar */}
        <div className="border-b border-[#b7ffe5]/10 bg-[#07110f]/55 px-5 py-5 md:px-8 flex items-center justify-between backdrop-blur-xl">
          <div>
            <div className="mb-1 font-mono text-[9px] uppercase tracking-[.2em] text-[#628378]">{currentSection?.label ?? 'Control plane'} / live workspace</div>
            <h1 className="font-sans font-semibold text-2xl tracking-tight text-[#eafff7] leading-tight">{title}</h1>
            {subtitle && (
              <p className="font-mono text-[11px] text-[#8eb1a5] tracking-wide mt-1">{subtitle}</p>
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
