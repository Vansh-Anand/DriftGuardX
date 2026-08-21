import Link from "next/link";

const MARQUEE_WORDS = [
  "TRACE FABRIC",
  "—",
  "CAUSAL GRAPHS",
  "—",
  "POLICY-GATED RECOVERY",
  "—",
  "COUNTERFACTUAL REPLAY",
  "—",
  "SEMANTIC DRIFT",
  "—",
  "DETERMINISTIC VERIFIER",
  "—",
  "MERKLE INTEGRITY",
  "—",
  "VERSIONED EXECUTION",
  "—",
  "BUDGET-CONSTRAINED BANDIT",
  "—",
];

export function Footer() {
  const marqueeText = [...MARQUEE_WORDS, ...MARQUEE_WORDS].join("  ");

  return (
    <footer className="w-full bg-[#ECEAE2] border-t border-[#0a0a0a] mt-0">
      {/* Scrolling ticker like 2xA's bottom bar */}
      <div className="border-b border-[#0a0a0a] overflow-hidden py-2">
        <div className="marquee-track inline-flex gap-12">
          {[...MARQUEE_WORDS, ...MARQUEE_WORDS].map((word, i) => (
            <span key={i} className="font-mono text-xs tracking-[0.2em] uppercase whitespace-nowrap text-[#0a0a0a]">
              {word}
            </span>
          ))}
        </div>
      </div>

      {/* Main footer grid */}
      <div className="border-b border-[#0a0a0a]">
        <div className="grid grid-cols-2 md:grid-cols-4">
          {/* Col 1: Brand */}
          <div className="border-r border-[#0a0a0a] p-8 flex flex-col justify-between min-h-[200px]">
            <div>
              <span className="font-mono text-xs tracking-[0.2em] uppercase font-bold block mb-2">DriftGuard-X</span>
              <span className="font-mono text-xs text-[#888] block">Patent-Ready</span>
              <span className="font-mono text-xs text-[#888] block">Agentic RAG Reliability</span>
            </div>
            <span className="font-mono text-xs text-[#888]">v2.0.0-beta</span>
          </div>

          {/* Col 2: Build */}
          <div className="border-r border-[#0a0a0a] p-8">
            <h4 className="font-mono text-xs tracking-[0.15em] uppercase mb-6">Build</h4>
            <div className="flex flex-col gap-3">
              <Link href="/dashboard" className="font-mono text-xs text-[#888] hover:text-[#0a0a0a] transition-colors link-underline">Dashboard ↗</Link>
              <Link href="/experiments" className="font-mono text-xs text-[#888] hover:text-[#0a0a0a] transition-colors link-underline">Experiments ↗</Link>
              <a href="#" className="font-mono text-xs text-[#888] hover:text-[#0a0a0a] transition-colors link-underline">Documentation ↗</a>
              <a href="https://github.com" className="font-mono text-xs text-[#888] hover:text-[#0a0a0a] transition-colors link-underline">GitHub ↗</a>
            </div>
          </div>

          {/* Col 3: Platform */}
          <div className="border-r border-[#0a0a0a] p-8">
            <h4 className="font-mono text-xs tracking-[0.15em] uppercase mb-6">Platform</h4>
            <div className="flex flex-col gap-3">
              <Link href="/recovery" className="font-mono text-xs text-[#888] hover:text-[#0a0a0a] transition-colors link-underline">Recovery Console ↗</Link>
              <Link href="/ledger" className="font-mono text-xs text-[#888] hover:text-[#0a0a0a] transition-colors link-underline">Certificate Ledger ↗</Link>
              <Link href="/security" className="font-mono text-xs text-[#888] hover:text-[#0a0a0a] transition-colors link-underline">Security Posture ↗</Link>
              <Link href="/scheduler" className="font-mono text-xs text-[#888] hover:text-[#0a0a0a] transition-colors link-underline">BCRB Scheduler ↗</Link>
            </div>
          </div>

          {/* Col 4: About */}
          <div className="p-8">
            <h4 className="font-mono text-xs tracking-[0.15em] uppercase mb-6">About</h4>
            <div className="flex flex-col gap-3">
              <a href="#" className="font-mono text-xs text-[#888] hover:text-[#0a0a0a] transition-colors link-underline">Whitepaper</a>
              <a href="#" className="font-mono text-xs text-[#888] hover:text-[#0a0a0a] transition-colors link-underline">Security Policy</a>
              <a href="#" className="font-mono text-xs text-[#888] hover:text-[#0a0a0a] transition-colors link-underline">Patent Evidence</a>
              <a href="#" className="font-mono text-xs text-[#888] hover:text-[#0a0a0a] transition-colors link-underline">Limitations</a>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom bar */}
      <div className="flex justify-between items-center px-8 py-4">
        <span className="font-mono text-xs text-[#888] tracking-widest">© 2026 DRIFTGUARD-X — RESEARCH PROTOTYPE</span>
        <div className="flex gap-8">
          <a href="#" className="font-mono text-xs text-[#888] hover:text-[#0a0a0a] transition-colors tracking-widest uppercase">Privacy</a>
          <a href="#" className="font-mono text-xs text-[#888] hover:text-[#0a0a0a] transition-colors tracking-widest uppercase">Terms</a>
          <a href="https://github.com" className="font-mono text-xs text-[#888] hover:text-[#0a0a0a] transition-colors tracking-widest uppercase">GitHub ↗</a>
        </div>
      </div>
    </footer>
  );
}
