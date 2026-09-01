"use client";

import Link from "next/link";
import { motion, useScroll, useTransform } from "framer-motion";
import {
  ArrowDownRight,
  ArrowUpRight,
  Check,
  FileCheck2,
  Fingerprint,
  GitBranch,
  Play,
  Radar,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useRef } from "react";

const SYSTEMS = [
  { id: "01", title: "Trace fabric", note: "Versioned observability", href: "/timeline", color: "#a7f3d0" },
  { id: "02", title: "Causal graph", note: "Evidence-backed attribution", href: "/graph", color: "#c4b5fd" },
  { id: "03", title: "Replay lab", note: "Killable counterfactuals", href: "/replay", color: "#fef08a" },
  { id: "04", title: "Recovery gate", note: "Policy-bound action", href: "/recovery", color: "#fecaca" },
];

const WORKFLOWS = [
  {
    title: "Diagnose agent drift",
    copy: "Build a tenant-scoped causal graph from live spans.",
    href: "/graph",
    icon: GitBranch,
    media: "/media/neural-network.jpg",
  },
  {
    title: "Replay the failure",
    copy: "Run deterministic counterfactuals inside a killable boundary.",
    href: "/replay",
    icon: Play,
    media: "/media/neural-network.jpg",
  },
  {
    title: "Seal evidence",
    copy: "Bind replay class, version, policy, and manifest into a certificate.",
    href: "/ledger",
    icon: FileCheck2,
    media: "/media/neural-network.jpg",
  },
];

const reveal = {
  hidden: { opacity: 0, y: 52 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.8, ease: [0.22, 1, 0.36, 1] as const } },
};

export default function LandingPage() {
  const visionRef = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({ target: visionRef, offset: ["start end", "end start"] });
  const mediaY = useTransform(scrollYProgress, [0, 1], ["-8%", "8%"]);

  return (
    <div className="editorial-site">
      <section className="hero-stage">
        <div className="hero-kicker">
          <span>Reliability infrastructure for agentic AI</span>
          <span className="hidden sm:inline">Research release · 2.0.0-rc.1</span>
        </div>

        <motion.div
          className="hero-media"
          initial={{ clipPath: "inset(42% 28% 42% 28% round 2px)" }}
          animate={{ clipPath: "inset(0% 0% 0% 0% round 0px)" }}
          transition={{ duration: 1.35, delay: 0.15, ease: [0.76, 0, 0.24, 1] }}
        >
          <video autoPlay muted loop playsInline poster="/media/neural-network.jpg" aria-label="Abstract data network animation">
            <source src="/media/data-network.mp4" type="video/mp4" />
          </video>
          <div className="hero-shade" />
          <div className="hero-grid" aria-hidden="true" />
        </motion.div>

        <motion.div className="hero-copy" initial="hidden" animate="visible" variants={reveal}>
          <p className="eyebrow text-white/60">Trace / isolate / replay / recover</p>
          <h1>
            Evidence,
            <span>not instinct.</span>
          </h1>
          <div className="hero-bottom-copy">
            <p>See why an agent failed. Prove the smallest safe intervention. Keep synthetic and real evidence unmistakably separate.</p>
            <Link href="/dashboard" className="round-action" aria-label="Open operations console">
              <ArrowDownRight size={25} />
            </Link>
          </div>
        </motion.div>

        <div className="edge-label"><strong>DGX</strong><span>Evidence system</span></div>
      </section>

      <section className="agent-launchpad" aria-label="DriftGuard-X workflow launchpad">
        <motion.div
          className="launchpad-shell"
          variants={reveal}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.25 }}
        >
          <div className="launchpad-heading">
            <p className="eyebrow">Operations launchpad</p>
            <h2>What needs proof today?</h2>
          </div>
          <div className="prompt-composer">
            <Search size={18} />
            <span>Investigate stale retrieval in the support agent and prepare a bounded recovery certificate</span>
            <Link href="/dashboard" aria-label="Open dashboard from launchpad">
              <ArrowUpRight size={18} />
            </Link>
          </div>
          <div className="launchpad-filters" aria-label="Workflow filters">
            {["All", "Trace", "Replay", "Policy", "Ledger", "Reports"].map((filter) => (
              <span key={filter} className={filter === "All" ? "active" : ""}>{filter}</span>
            ))}
          </div>
          <div className="workflow-grid">
            {WORKFLOWS.map(({ title, copy, href, icon: Icon, media }, index) => (
              <Link key={title} href={href} className="workflow-card">
                <img src={media} alt="" aria-hidden="true" />
                <div className="workflow-card-top">
                  <span><Icon size={14} /> {index === 0 ? "Featured" : "Ready"}</span>
                  <ArrowUpRight size={16} />
                </div>
                <div>
                  <h3>{title}</h3>
                  <p>{copy}</p>
                </div>
              </Link>
            ))}
            <Link href="/experiments" className="workflow-card workflow-card-accent">
              <Sparkles size={20} />
              <div>
                <h3>Compare evidence classes</h3>
                <p>Keep synthetic benchmark claims separate from controlled replay evidence before release.</p>
              </div>
              <span>Open experiments <ArrowUpRight size={16} /></span>
            </Link>
          </div>
        </motion.div>
      </section>

      <section className="capability-index">
        <motion.div className="section-intro" variants={reveal} initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.3 }}>
          <p className="eyebrow">The control plane</p>
          <h2>One reliability system.<br /><em>Four evidence loops.</em></h2>
          <p className="section-copy">A deliberately bounded operating surface for tracing, causal localization, deterministic replay, and governed recovery.</p>
        </motion.div>

        <div className="system-list">
          {SYSTEMS.map((system, index) => (
            <motion.div key={system.id} initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }} transition={{ delay: index * 0.08 }}>
              <Link href={system.href} className="system-row" style={{ "--row-accent": system.color } as React.CSSProperties}>
                <span className="system-id">{system.id}</span>
                <span className="system-title">{system.title}</span>
                <span className="system-note">{system.note}</span>
                <ArrowUpRight className="system-arrow" />
              </Link>
            </motion.div>
          ))}
        </div>
      </section>

      <section className="case-collage">
        <div className="collage-label">
          <span>Selected surfaces</span>
          <span>Live console / controlled evidence</span>
        </div>
        <motion.article className="case-card case-observe" variants={reveal} initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.2 }}>
          <img src="/media/neural-network.jpg" alt="Abstract neural network visualization" />
          <div className="case-overlay">
            <Radar />
            <p>Watch every dependency<br />without losing provenance.</p>
          </div>
          <span>01 / Observe</span>
        </motion.article>
        <motion.article className="case-card case-console" variants={reveal} initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.2 }}>
          <div className="mini-console">
            <div className="mini-top"><span>LIVE TRACE</span><span className="live-pill">● HEALTHY</span></div>
            <div className="trace-orbit"><span /><i /><b /><em /></div>
            <div className="mini-metrics"><span>18.2k<small>spans</small></span><span>42ms<small>lag</small></span><span>0.3%<small>errors</small></span></div>
          </div>
          <span>02 / Understand</span>
        </motion.article>
        <motion.article className="case-card case-proof" variants={reveal} initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.2 }}>
          <div className="proof-panel">
            <Fingerprint size={58} strokeWidth={1} />
            <h3>Bound to evidence.</h3>
            {["Tenant scoped", "Replay confirmed", "Certificate sealed"].map(item => <p key={item}><Check size={14} />{item}</p>)}
          </div>
          <span>03 / Prove</span>
        </motion.article>
      </section>

      <section ref={visionRef} className="vision-stage">
        <motion.div className="vision-media" style={{ y: mediaY }}>
          <img src="/media/neural-network.jpg" alt="Teal neural network representing explainable agent operations" />
        </motion.div>
        <div className="vision-shade" />
        <motion.div className="vision-copy" variants={reveal} initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.4 }}>
          <p className="eyebrow text-white/60">Core vision</p>
          <h2>Make the invisible<br /><em>defensible.</em></h2>
          <p>Every intervention should have a bounded cause, reproducible replay, explicit evidence class, and verifiable certificate.</p>
        </motion.div>
      </section>

      <section className="trust-strip">
        {[
          [ShieldCheck, "Fail closed", "Production configuration rejects unsafe defaults."],
          [Radar, "See causality", "Attribution is confirmed through controlled replay."],
          [Fingerprint, "Seal provenance", "Version, policy, lock, and evidence remain bound."],
        ].map(([Icon, title, copy]) => {
          const Glyph = Icon as typeof ShieldCheck;
          return <article key={String(title)}><Glyph /><h3>{String(title)}</h3><p>{String(copy)}</p></article>;
        })}
      </section>

      <section className="closing-orbit">
        <div className="orbit-lines" aria-hidden="true"><span /><span /><i /></div>
        <p className="eyebrow">Start with the evidence</p>
        <h2>Enter the<br /><em>control plane.</em></h2>
        <Link href="/dashboard" className="capsule-link">Open console <ArrowUpRight size={18} /></Link>
      </section>
    </div>
  );
}
