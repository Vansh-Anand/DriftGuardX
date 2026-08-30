"use client";

import Link from "next/link";
import { motion, useScroll, useTransform } from "framer-motion";
import { ArrowDownRight, ArrowUpRight, Check, Fingerprint, Radar, ShieldCheck } from "lucide-react";
import { useRef } from "react";

const SYSTEMS = [
  { id: "01", title: "Trace fabric", note: "Versioned observability", href: "/timeline", color: "#a7f3d0" },
  { id: "02", title: "Causal graph", note: "Evidence-backed attribution", href: "/graph", color: "#c4b5fd" },
  { id: "03", title: "Replay lab", note: "Killable counterfactuals", href: "/replay", color: "#fef08a" },
  { id: "04", title: "Recovery gate", note: "Policy-bound action", href: "/recovery", color: "#fecaca" },
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
