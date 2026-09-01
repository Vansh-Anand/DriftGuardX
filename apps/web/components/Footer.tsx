import Link from "next/link";
import buildMetadata from "@/src/generated/build-metadata.json";

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
  return (
    <footer className="w-full bg-background border-t border-foreground/20 mt-0 text-foreground">
      {/* Main footer grid (Blueprint Title Block Style) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 border-b border-foreground/20">
        
        {/* Large Logo Block */}
        <div className="lg:col-span-3 border-r border-foreground/20 p-8 flex flex-col justify-between min-h-[300px] relative crosshair-corner crosshair-br">
          <div className="flex flex-col gap-2">
            <span className="font-bold text-2xl uppercase tracking-tighter block mb-2">DRIFTGUARDX</span>
            <span className="mono text-muted block">AN AI AGENT THAT WORKS INSIDE YOUR DATA PIPELINES.</span>
          </div>
          <svg viewBox="0 0 100 100" className="absolute bottom-8 right-8 w-32 h-32 fill-none stroke-foreground/10 stroke-[2]" strokeLinecap="round" strokeLinejoin="round">
               <polygon points="50 10 10 30 50 50 90 30 50 10" />
               <polyline points="10 70 50 90 90 70" />
               <polyline points="10 50 50 70 90 50" />
               <line x1="50" y1="50" x2="50" y2="90" />
          </svg>
        </div>

        {/* Links Grid */}
        <div className="lg:col-span-9 grid grid-cols-2 md:grid-cols-4">
          
          <div className="border-r border-foreground/20 p-8">
            <h4 className="mono font-bold mb-6">COMPANY</h4>
            <div className="flex flex-col gap-3">
              <Link href="/" className="mono text-muted hover:text-accent transition-colors">Home</Link>
              <Link href="#" className="mono text-muted hover:text-foreground transition-colors">About us</Link>
              <Link href="#" className="mono text-muted hover:text-foreground transition-colors">Contact us</Link>
            </div>
          </div>

          <div className="border-r border-foreground/20 p-8">
            <h4 className="mono font-bold mb-6">PRODUCT</h4>
            <div className="flex flex-col gap-3">
              <Link href="/dashboard" className="mono text-muted hover:text-foreground transition-colors">Dashboard</Link>
              <Link href="/experiments" className="mono text-muted hover:text-foreground transition-colors">Experiments</Link>
              <Link href="/reports" className="mono text-muted hover:text-foreground transition-colors">Reports</Link>
            </div>
          </div>

          <div className="border-r border-foreground/20 p-8">
            <h4 className="mono font-bold mb-6">RESOURCES</h4>
            <div className="flex flex-col gap-3">
              <Link href="/recovery" className="mono text-muted hover:text-foreground transition-colors">Recovery Console</Link>
              <Link href="/ledger" className="mono text-muted hover:text-foreground transition-colors">Certificate Ledger</Link>
              <Link href="/security" className="mono text-muted hover:text-foreground transition-colors">Security Posture</Link>
            </div>
          </div>

          <div className="p-8">
            <h4 className="mono font-bold mb-6">SYSTEM</h4>
            <div className="flex flex-col gap-3">
              <span className="mono text-muted">v{buildMetadata.version}</span>
              <span className="mono text-muted">{buildMetadata.verification}</span>
              <a href="https://github.com/Vansh-Anand/DriftGuardX" className="mono text-muted hover:text-foreground transition-colors">GitHub ↗</a>
            </div>
          </div>

        </div>
      </div>

      {/* Large Outline Text Block */}
      <div className="border-b border-foreground/20 p-4 overflow-hidden relative h-48 flex items-center justify-center">
         {/* Very large outlined text */}
         <h1 className="text-[12vw] font-bold tracking-tighter text-transparent" style={{ WebkitTextStroke: '1px var(--foreground)', opacity: 0.2 }}>
            DRIFTGUARDX
         </h1>
         {/* Interactive red dot in the middle of nowhere */}
         <div className="absolute right-1/4 bottom-1/3 red-square" />
      </div>

      {/* Bottom bar */}
      <div className="flex justify-between items-center px-8 py-4">
        <span className="mono text-muted">© 2026 DRIFTGUARD-X. ALL RIGHTS RESERVED. CONCEPT CRAFTED BY BEARPLUS.</span>
        <div className="flex gap-8">
          <a href="#" className="mono text-muted hover:text-foreground transition-colors">PRIVACY</a>
          <a href="#" className="mono text-muted hover:text-foreground transition-colors">TERMS</a>
        </div>
      </div>
    </footer>
  );
}
