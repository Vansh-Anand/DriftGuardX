"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

// ─── Live counter animation ────────────────────────────────────────────────────
function AnimatedNumber({ target, suffix = "" }: { target: string; suffix?: string }) {
  return (
    <span className="font-mono tabular-nums">{target}{suffix}</span>
  );
}

// ─── Scrolling horizontal label row (2xA style) ────────────────────────────────
function MarqueeRow({ words, dark = false }: { words: string[]; dark?: boolean }) {
  const all = [...words, ...words];
  return (
    <div className={`overflow-hidden py-3 border-b ${dark ? "border-[#333] bg-[#0a0a0a]" : "border-[#0a0a0a] bg-[#ECEAE2]"}`}>
      <div className="marquee-track inline-flex gap-10">
        {all.map((w, i) => (
          <span key={i} className={`font-mono text-xs tracking-[0.25em] uppercase whitespace-nowrap ${dark ? "text-[#555]" : "text-[#0a0a0a]/40"}`}>
            {w}
          </span>
        ))}
      </div>
    </div>
  );
}

// ─── Feature row (table-style like 2xA project list) ──────────────────────────
const FEATURES = [
  { index: "01", name: "Trace Fabric", href: "/timeline", tag: "Observability", desc: "Versioned execution spans, redaction, parentage and provenance graphs. Every token auditable." },
  { index: "02", name: "Causal Graph", href: "/graph", tag: "Attribution", desc: "Dependency DAG connecting component failures to downstream symptoms with attribution scores." },
  { index: "03", name: "Counterfactual Replay", href: "/replay", tag: "Diagnostics", desc: "Version-pinned synthetic replay. Budget-constrained intervention candidate scheduling." },
  { index: "04", name: "Diagnosis Engine", href: "/rationale", tag: "Detection", desc: "Statistical detectors, graph construction and GAT fault localisation across multi-agent pipelines." },
  { index: "05", name: "Policy-Gated Recovery", href: "/recovery", tag: "Governance", desc: "Allowlisted actions, policy gates, canaries, certificates and a deterministic verifier." },
  { index: "06", name: "Certificate Ledger", href: "/ledger", tag: "Integrity", desc: "Tamper-evident append-only cryptographic audit log. Every recovery action signed and witnessed." },
];

const MARQUEE_LABELS = ["TRACE", "—", "DETECT", "—", "REPLAY", "—", "RECOVER", "—", "CERTIFY", "—", "GOVERN", "—"];

export default function LandingPage() {
  const [scrollY, setScrollY] = useState(0);
  useEffect(() => {
    const onScroll = () => setScrollY(window.scrollY);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className="w-full">

      {/* ── HERO ── */}
      <section className="min-h-[90vh] flex flex-col border-b border-[#0a0a0a]">

        {/* Top label row */}
        <div className="grid grid-cols-[1fr_auto_auto] border-b border-[#0a0a0a] px-8 py-3 items-center">
          <span className="font-mono text-xs text-[#888] uppercase tracking-[0.15em]">On Reliability as a Way of Thinking</span>
          <span className="font-mono text-xs text-[#888] uppercase tracking-[0.15em] hidden md:block">Agentic RAG</span>
          <span className="font-mono text-xs text-[#888] uppercase tracking-[0.15em] pl-8 hidden md:block">Invention Candidate</span>
        </div>

        {/* Main hero area */}
        <div className="flex-1 grid grid-cols-1 md:grid-cols-[1fr_1fr] relative">
          
          {/* Left: Giant heading */}
          <div className="border-r border-[#0a0a0a] p-10 flex flex-col justify-between">
            <div>
              <h1
                className="font-sans font-bold leading-[0.88] tracking-tight text-[#0a0a0a]"
                style={{ fontSize: "clamp(80px, 10vw, 160px)" }}
              >
                Drift
                <br />
                Guard
                <br />
                <span className="text-[#0a0a0a]">X</span>
              </h1>
            </div>
            <div className="mt-8 flex flex-col gap-4">
              <p className="font-mono text-xs tracking-[0.12em] uppercase text-[#888] max-w-xs">
                An experimental framework for evaluating Budget-Constrained Counterfactual Replay in Agentic RAG systems.
              </p>
              <div className="flex gap-4 pt-2">
                <Link
                  href="/dashboard"
                  className="font-mono text-xs tracking-widest uppercase border border-[#0a0a0a] px-6 py-2.5 bg-[#0a0a0a] text-[#ECEAE2] hover:bg-transparent hover:text-[#0a0a0a] transition-colors"
                >
                  Open Console
                </Link>
                <Link
                  href="/experiments"
                  className="font-mono text-xs tracking-widest uppercase border border-[#0a0a0a] px-6 py-2.5 hover:bg-[#0a0a0a] hover:text-[#ECEAE2] transition-colors"
                >
                  Experiments ↗
                </Link>
              </div>
            </div>
          </div>

          {/* Right: ASCII art / data visualization panel */}
          <div className="bg-[#0a0a0a] relative overflow-hidden flex flex-col justify-between p-10 min-h-[500px]">
            {/* Simulated ASCII trace output */}
            <div className="font-mono text-[10px] leading-[1.6] text-[#555] select-none pointer-events-none overflow-hidden absolute inset-0 p-10">
              {`span_id=a1b2c3 tenant=T_111 component=retriever/v1 status=OK latency=142ms
span_id=d4e5f6 tenant=T_111 component=reranker/v1 status=OK latency=38ms
span_id=g7h8i9 tenant=T_111 component=generator/v1 status=OK latency=891ms faithfulness=0.90
span_id=j0k1l2 tenant=T_111 component=policy_check/v1 decision=allow rule=ALLOW_SYNTHETIC_READ
─────────────────────────────────────────────────────────────────────────
merkle_root=e3b0c44298fc1c149afbf4...  LEAF_DOMAIN=0x00  INT_DOMAIN=0x01
drift_score=0.04  threshold=0.15  decision=NO_DRIFT  model=cosine_v1
─────────────────────────────────────────────────────────────────────────
replay_id=r9s8t7 seed=42 status=COMPLETED intervention=SWAP_RETRIEVER
reliability_delta={faithfulness:+0.55, latency:-120ms, cost:-0.02}
canary.qualityPass=true  canary.safetyPass=true  overall=PASSED
─────────────────────────────────────────────────────────────────────────
cert_id=cert_1a2b3c timestamp=2026-08-21T17:30:00Z action=rollback_retriever
cert_hash=59a597a7605e557b7f1981d1...  witness=IN_MEMORY  status=VERIFIED
─────────────────────────────────────────────────────────────────────────
quarantine_check tenant=T_222 partition=T_222_data role=agent PASS
quarantine_check tenant=T_111 partition=T_222_data role=agent DENIED
`.split('\n').map((line, i) => (
              <div key={i} className="whitespace-nowrap">{line}</div>
            ))}
            </div>
            {/* Yellow accent box */}
            <div className="absolute bottom-10 right-10 bg-[#E8FF00] px-6 py-4">
              <span className="font-mono text-xs text-[#0a0a0a] font-bold uppercase tracking-widest block">CI Verification</span>
              <span className="font-mono text-xs text-[#0a0a0a]/60 uppercase tracking-wider">Run the verified suite</span>
            </div>
          </div>
        </div>

        {/* Bottom scrolling label */}
        <MarqueeRow words={MARQUEE_LABELS} />
      </section>

      {/* ── CAPABILITIES / FEATURE LIST ── */}
      <section className="border-b border-[#0a0a0a]">
        {/* Section header */}
        <div className="grid grid-cols-[auto_1fr] border-b border-[#0a0a0a]">
          <div className="border-r border-[#0a0a0a] px-8 py-5">
            <span className="font-mono text-xs tracking-[0.2em] uppercase text-[#888]">Capabilities</span>
          </div>
          <div className="px-8 py-5 flex justify-between items-center">
            <h2 className="font-sans font-bold text-3xl md:text-5xl tracking-tight">Selected Systems</h2>
            <Link href="/dashboard" className="font-mono text-xs tracking-widest uppercase link-underline hidden md:block">
              View All (6) →
            </Link>
          </div>
        </div>

        {/* Feature rows — 2xA project list style */}
        {FEATURES.map((f, i) => (
          <Link
            key={f.index}
            href={f.href}
            className="grid grid-cols-[60px_1fr_auto] md:grid-cols-[60px_1fr_300px_120px] border-b border-[#0a0a0a] hover:bg-[#0a0a0a] hover:text-[#ECEAE2] transition-colors group px-8 py-6 gap-6 items-start"
          >
            <span className="font-mono text-xs text-[#888] group-hover:text-[#555] pt-1">{f.index}</span>
            <div>
              <h3 className="font-sans font-bold text-2xl md:text-3xl mb-2 leading-tight">{f.name}</h3>
              <p className="font-mono text-xs text-[#888] group-hover:text-[#aaa] max-w-md leading-relaxed">{f.desc}</p>
            </div>
            <div className="hidden md:flex items-start pt-1">
              <span className="font-mono text-xs border border-current px-3 py-1 tracking-widest uppercase">{f.tag}</span>
            </div>
            <div className="hidden md:flex items-start justify-end pt-1">
              <span className="font-mono text-xs tracking-widest">↗</span>
            </div>
          </Link>
        ))}
      </section>

      {/* ── STATS (2xA big number style) ── */}
      <section className="border-b border-[#0a0a0a]">
        {/* Section heading spread across columns */}
        <div className="grid grid-cols-2 md:grid-cols-4 font-mono text-xs tracking-[0.2em] uppercase text-[#0a0a0a]/30 border-b border-[#0a0a0a]">
          {["Built", "With", "Adversarial", "Rigour"].map((w, i) => (
            <div key={i} className={`py-3 px-8 ${i < 3 ? "border-r border-[#0a0a0a]/20" : ""}`}>{w}</div>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3">
          <div className="border-r border-[#0a0a0a] p-12 flex flex-col gap-2">
            <span className="font-sans font-bold text-7xl md:text-9xl leading-none tracking-tighter">CI</span>
            <span className="font-mono text-xs text-[#888] tracking-widest uppercase mt-4">Verification Required</span>
            <span className="font-mono text-xs text-[#888]">Unit · Integration · Contract · Security</span>
          </div>
          <div className="border-r border-[#0a0a0a] p-12 flex flex-col gap-2">
            <span className="font-sans font-bold text-7xl md:text-9xl leading-none tracking-tighter">20</span>
            <span className="font-mono text-xs text-[#888] tracking-widest uppercase mt-4">Adversarial Fixes</span>
            <span className="font-mono text-xs text-[#888]">Cryptographic · Semantic · Runtime</span>
          </div>
          <div className="p-12 flex flex-col gap-2">
            <span className="font-sans font-bold text-7xl md:text-9xl leading-none tracking-tighter">&lt;30s</span>
            <span className="font-mono text-xs text-[#888] tracking-widest uppercase mt-4">Replay Hard Timeout</span>
            <span className="font-mono text-xs text-[#888]">Resource-bounded execution</span>
          </div>
        </div>
      </section>

      {/* ── CTA SECTION (dark) ── */}
      <section className="bg-[#0a0a0a] text-[#ECEAE2] border-b border-[#333]">
        {/* Marquee on dark bg */}
        <MarqueeRow words={MARQUEE_LABELS} dark />

        <div className="grid grid-cols-1 md:grid-cols-2 min-h-[400px]">
          <div className="border-r border-[#333] p-12 flex flex-col justify-between">
            <div>
              <span className="font-mono text-xs tracking-[0.2em] uppercase text-[#555] block mb-6">Ready to Explore?</span>
              <h2 className="font-sans font-bold text-5xl md:text-7xl leading-[0.9] tracking-tight">
                Open the<br/>Console.
              </h2>
            </div>
            <div className="flex gap-4">
              <Link
                href="/dashboard"
                className="font-mono text-xs tracking-widest uppercase border border-[#ECEAE2] px-8 py-3 bg-[#ECEAE2] text-[#0a0a0a] hover:bg-transparent hover:text-[#ECEAE2] transition-colors"
              >
                Dashboard
              </Link>
              <Link
                href="/security"
                className="font-mono text-xs tracking-widest uppercase border border-[#555] px-8 py-3 hover:border-[#ECEAE2] transition-colors"
              >
                Security ↗
              </Link>
            </div>
          </div>

          <div className="p-12 flex flex-col justify-between">
            <div className="font-mono text-xs text-[#555] tracking-[0.12em] uppercase mb-6">Patent Evidence Bounds</div>
            <div className="space-y-4">
              {[
                ["Causal Isolation", "Replay-confirmed attribution, not correlation"],
                ["Cryptographic Integrity", "Domain-separated Merkle DAG canonicalization"],
                ["Policy Enforcement", "Fail-closed tenant-aware quarantine boundaries"],
                ["Semantic Verification", "Vector-based drift, not string equality"],
              ].map(([title, desc]) => (
                <div key={title} className="border-t border-[#222] pt-4">
                  <span className="font-mono text-xs text-[#ECEAE2] tracking-widest uppercase block">{title}</span>
                  <span className="font-mono text-xs text-[#555] mt-1 block">{desc}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

    </div>
  );
}
