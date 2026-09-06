"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Plus } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground font-sans relative pb-32 overflow-x-hidden">
      {/* Drafting Guidelines (Background grid is handled in globals.css) */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden opacity-20">
        <div className="absolute top-0 bottom-0 left-[10%] w-px bg-foreground" />
        <div className="absolute top-0 bottom-0 right-[10%] w-px bg-foreground" />
        <div className="absolute left-0 right-0 top-[20%] h-px bg-foreground" />
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-6 md:px-12 pt-32">
        {/* Top Info Block */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-24 text-xs font-mono uppercase tracking-widest border-t border-b border-foreground/20 py-4 crosshair-corner crosshair-tl crosshair-tr crosshair-bl crosshair-br">
          <div className="col-span-1 md:col-span-2">
            <h1 className="text-3xl md:text-5xl font-bold tracking-tighter mb-2">DRIFTGUARDX.</h1>
            <p className="text-muted">THE AWARD-WINNING<br/>RAG RELIABILITY PLATFORM</p>
          </div>
          <div className="flex flex-col gap-2">
            <div className="flex justify-between">
              <span className="text-muted">TYPE</span>
              <span>DATA RELIABILITY INFRASTRUCTURE</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">FOCUS</span>
              <span>AGENTIC RAG TRACING</span>
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <span className="text-muted">SYSTEMS</span>
            <span>001 INITIALIZE CORE SYSTEM</span>
            <span>002 LOAD AI MODELS</span>
            <span>003 CONFIGURE DATA PIPELINES</span>
          </div>
        </div>

        {/* Hero Illustration */}
        <div className="relative w-full aspect-video border border-foreground/20 bg-[#F4F4F0] flex items-center justify-center overflow-hidden crosshair-corner crosshair-tl crosshair-tr crosshair-bl crosshair-br mb-24">
          <svg className="absolute inset-0 w-full h-full" viewBox="0 0 1000 500" preserveAspectRatio="xMidYMid slice">
            {/* Architectural structural lines */}
            <g stroke="#090B0A" strokeWidth="1" opacity="0.3" fill="none">
              <rect x="250" y="100" width="500" height="300" />
              <rect x="300" y="150" width="400" height="200" />
              <line x1="250" y1="250" x2="750" y2="250" />
              <line x1="500" y1="100" x2="500" y2="400" />
              <line x1="0" y1="350" x2="1000" y2="350" />
              {/* Stairs/abstract blocks */}
              <path d="M 200 400 L 250 400 L 250 350" />
              <path d="M 150 450 L 200 450 L 200 400" />
              <path d="M 100 500 L 150 500 L 150 450" />
            </g>
            
            {/* Red accent line running through architecture */}
            <line x1="0" y1="250" x2="1000" y2="250" stroke="#FF2400" strokeWidth="1.5" className="animate-draw" />
          </svg>

          {/* Interactive Red Markers */}
          <div className="absolute top-[30%] left-[35%] group">
            <div className="red-square" />
            <div className="absolute left-6 top-0 w-64 bg-background border border-foreground p-3 opacity-0 group-hover:opacity-100 transition-opacity z-20 pointer-events-none">
              <p className="mono font-bold border-b border-foreground/20 pb-1 mb-2">DGX [01]</p>
              <p className="text-xs">Data Drift Detected in Embedding Space. Replaying counterfactuals to isolate the root cause.</p>
            </div>
          </div>

          <div className="absolute top-[65%] left-[60%] group">
            <div className="red-square" />
            <div className="absolute left-6 top-0 w-64 bg-background border border-foreground p-3 opacity-0 group-hover:opacity-100 transition-opacity z-20 pointer-events-none">
              <p className="mono font-bold border-b border-foreground/20 pb-1 mb-2">DGX [02]</p>
              <p className="text-xs">Policy Violation: Unsafe output identified. Initiating recovery gate and blocking response.</p>
            </div>
          </div>
        </div>

        {/* Big Statement Section */}
        <div className="flex flex-col md:flex-row justify-between items-start gap-12 border-b border-foreground/20 pb-24 relative crosshair-corner crosshair-bl crosshair-br">
          <Plus className="absolute -left-3 -top-3 text-muted" size={24} strokeWidth={1} />
          <h2 className="text-5xl md:text-7xl font-bold tracking-tighter leading-none uppercase max-w-3xl">
            An AI agent that works inside your data pipelines
          </h2>
          <div className="max-w-sm flex flex-col gap-6">
            <p className="text-lg leading-tight">
              DriftGuardX reviews your causal graphs, identifies drift, and proposes counterfactuals. Upon approval, it recovers automatically. The concept crafted for data reliability teams.
            </p>
            <Link href="/dashboard" className="mono inline-flex items-center gap-2 link-underline w-fit group">
              DISCOVER MORE <ArrowRight size={14} className="group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>
        </div>

        {/* Iterations Bar */}
        <div className="flex justify-between items-center py-4 border-b border-foreground/20 overflow-x-auto whitespace-nowrap mono text-muted">
          <span className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full border border-muted" /> FASTER ITERATIONS</span>
          <span className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full border border-muted" /> FEWER MISTAKES</span>
          <span className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full border border-muted" /> LESS BUSYWORK</span>
          <span className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full border border-muted" /> FASTER ITERATIONS</span>
          <span className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full border border-muted" /> FEWER MISTAKES</span>
        </div>

        {/* Second Visual Area */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mt-24">
          <div className="relative aspect-square border border-foreground/20 p-8 flex flex-col justify-between">
            <h3 className="text-4xl font-bold uppercase tracking-tighter leading-none">
              The repetitive parts of monitoring shouldn't eat your day.
            </h3>
            <div className="absolute inset-0 z-0 opacity-10 flex items-center justify-center overflow-hidden pointer-events-none">
                <svg viewBox="0 0 100 100" className="w-full h-full scale-150">
                    <circle cx="50" cy="50" r="40" stroke="#090B0A" strokeWidth="0.5" fill="none" />
                    <circle cx="50" cy="50" r="30" stroke="#090B0A" strokeWidth="0.5" fill="none" />
                    <line x1="50" y1="0" x2="50" y2="100" stroke="#090B0A" strokeWidth="0.5" />
                    <line x1="0" y1="50" x2="100" y2="50" stroke="#090B0A" strokeWidth="0.5" />
                </svg>
            </div>
            
            <div className="relative z-10 bg-accent text-background w-32 h-32 rounded-full flex items-center justify-center self-end mix-blend-multiply">
              {/* Red Circle Accent purely for visual weight */}
            </div>
            
            <Link href="/dashboard" className="mono inline-flex items-center gap-2 link-underline w-fit mt-8 z-10">
              LEARN MORE <ArrowRight size={14} />
            </Link>
          </div>
          <div className="border border-foreground/20 relative p-8 crosshair-corner crosshair-tl crosshair-br">
            <div className="absolute top-4 left-4 red-square" />
            <div className="absolute bottom-4 right-4 red-square" />
            <p className="mono mb-4">[02]</p>
            <h3 className="text-2xl font-bold uppercase mb-8">DGX DASHBOARD</h3>
            <div className="w-full h-64 border border-foreground/10 bg-white shadow-sm flex flex-col p-4 relative overflow-hidden">
               <div className="flex justify-between border-b border-foreground/10 pb-2 mb-4 mono">
                  <span>ACTIVE SPANS: 18.2K</span>
                  <span className="text-accent flex items-center gap-1"><div className="w-2 h-2 bg-accent rounded-full animate-pulse"/> LIVE</span>
               </div>
               <div className="flex-1 border-l-2 border-accent pl-4 flex flex-col justify-center gap-4">
                  <div className="h-2 w-3/4 bg-foreground/10" />
                  <div className="h-2 w-1/2 bg-foreground/10" />
                  <div className="h-2 w-5/6 bg-foreground/10" />
               </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
