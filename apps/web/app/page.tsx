import Link from "next/link";
import { ArrowRight, Hexagon, Component, Blocks, Maximize } from "lucide-react";
import { AnimatedSection } from "@/components/AnimatedSection";

export default function LandingPage() {
  return (
    <div className="w-full">
      {/* Hero Section (Mint Green) */}
      <section className="bg-[#dcf6cc] pt-40 pb-32 px-6 w-full rounded-b-[40px] relative z-10">
        <div className="max-w-7xl mx-auto flex flex-col">
          <AnimatedSection>
            <h1 className="text-[120px] leading-[0.9] font-medium tracking-tight text-black mb-8 max-w-5xl">
              Reliability for<br/>
              Agentic RAG.
            </h1>
          </AnimatedSection>
          
          <div className="flex justify-between items-end mt-12">
            <AnimatedSection delay={0.1}>
              <Link 
                href="/dashboard" 
                className="px-6 py-2 rounded-full border border-black text-black font-medium hover:bg-black hover:text-white transition-colors text-sm uppercase tracking-wide inline-flex items-center gap-2"
              >
                All Use Cases
              </Link>
            </AnimatedSection>
            
            <AnimatedSection delay={0.2} className="hidden md:block max-w-md">
              <p className="text-black/80 text-xl leading-snug">
                An experimental framework for evaluating Budget-Constrained Counterfactual Replay. Identify semantic drift, trace execution graphs, and ensure policy compliance on-chain and off-chain.
              </p>
            </AnimatedSection>
          </div>
        </div>
      </section>

      {/* Features Grid (Dark) */}
      <section className="bg-[#111] pt-24 pb-32 px-6 w-full -mt-10 pt-32">
        <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-6">
          <AnimatedSection delay={0.1}>
            <div className="bg-[#1a1a1a] border border-[#333] p-12 h-[500px] flex flex-col justify-between hover:border-white/20 transition-colors group relative overflow-hidden">
              <div>
                <h3 className="text-3xl font-medium mb-4 text-white">Policy-Gated Recovery</h3>
                <p className="text-[#888] text-lg max-w-sm">
                  Hierarchical policy engine governing mock recovery actions and issuing cryptographic ledgers of the rollback state.
                </p>
              </div>
              <div className="flex justify-between items-end">
                <Link href="/experiments" className="flex items-center gap-2 text-white/70 group-hover:text-white transition-colors text-sm uppercase tracking-wider">
                  <ArrowRight className="w-4 h-4" /> Discover
                </Link>
              </div>
              {/* Abstract Geometric Decoration */}
              <Hexagon className="absolute -bottom-20 -right-20 w-96 h-96 text-white/5 group-hover:text-white/10 transition-colors stroke-1" />
            </div>
          </AnimatedSection>

          <AnimatedSection delay={0.2}>
            <div className="bg-[#1a1a1a] border border-[#333] p-12 h-[500px] flex flex-col justify-between hover:border-white/20 transition-colors group relative overflow-hidden">
              <div>
                <h3 className="text-3xl font-medium mb-4 text-white">Diffusion Propagation</h3>
                <p className="text-[#888] text-lg max-w-sm">
                  Maps symptomatic drift backwards via analytical topological scoring across your entire multi-agent pipeline.
                </p>
              </div>
              <div className="flex justify-between items-end">
                <Link href="/experiments" className="flex items-center gap-2 text-white/70 group-hover:text-white transition-colors text-sm uppercase tracking-wider">
                  <ArrowRight className="w-4 h-4" /> Discover
                </Link>
              </div>
              {/* Abstract Geometric Decoration */}
              <Blocks className="absolute -bottom-20 -right-20 w-96 h-96 text-white/5 group-hover:text-white/10 transition-colors stroke-1" />
            </div>
          </AnimatedSection>

          <AnimatedSection delay={0.3} className="md:col-span-2">
            <div className="bg-[#1a1a1a] border border-[#333] p-12 h-[400px] flex flex-col justify-between hover:border-white/20 transition-colors group relative overflow-hidden">
              <div className="max-w-2xl relative z-10">
                <h3 className="text-4xl font-medium mb-4 text-white">Budget-Constrained Bandit</h3>
                <p className="text-[#888] text-xl">
                  Estimates optimal counterfactual interventions to limit compute waste during diagnostic replays. The next generation of reliability is here.
                </p>
              </div>
              <div className="flex justify-between items-end relative z-10">
                <Link href="/dashboard" className="flex items-center gap-2 text-white/70 group-hover:text-white transition-colors text-sm uppercase tracking-wider">
                  <ArrowRight className="w-4 h-4" /> Discover
                </Link>
              </div>
              {/* Abstract Geometric Decoration */}
              <Component className="absolute -bottom-40 right-10 w-[500px] h-[500px] text-white/5 group-hover:text-white/10 transition-colors stroke-1" />
            </div>
          </AnimatedSection>
        </div>
      </section>

      {/* Categories Section (Split Green/Dark) */}
      <section className="w-full flex flex-col md:flex-row min-h-[600px] border-t border-[#333]">
        <div className="md:w-1/2 bg-[#dcf6cc] p-16 md:p-24 flex flex-col justify-center text-black">
           <div className="text-xs font-bold uppercase tracking-widest mb-10 border border-black/20 rounded-full px-4 py-1 self-start">
             Use Cases Hub
           </div>
           <p className="text-sm uppercase tracking-wider mb-4 font-semibold opacity-70">DriftGuard-X Apps</p>
           <h2 className="text-6xl md:text-7xl font-medium leading-[0.9] mb-10">
             Redefine Entire Categories
           </h2>
           <p className="text-xl max-w-md">
             From AI to DePIN and digital commerce, DriftGuard-X provides the rails for the applications that define tomorrow's digital markets.
           </p>
        </div>
        <div className="md:w-1/2 bg-[#1a1a1a] p-16 flex items-center justify-center relative overflow-hidden">
           <Maximize className="w-full h-full max-w-[400px] max-h-[400px] text-[#333] stroke-1 absolute" />
        </div>
      </section>

      {/* Stats Section */}
      <section className="bg-[#1a1a1a] py-32 border-t border-[#333] relative overflow-hidden">
        {/* Striped border pattern top */}
        <div className="absolute top-0 left-0 w-full h-8 flex">
           {Array.from({length: 40}).map((_, i) => (
             <div key={i} className={`flex-1 h-full ${i % 2 === 0 ? 'bg-[#dcf6cc]' : 'bg-[#111]'}`} />
           ))}
        </div>
        
        <div className="max-w-4xl mx-auto px-6 text-center">
          <AnimatedSection>
            <h2 className="text-5xl md:text-7xl font-medium mb-8 text-white">Built for the Next Generation</h2>
            <p className="text-xl text-[#888] max-w-2xl mx-auto mb-20">
              Emerging technologies demand more than speed. They require infrastructure that can evolve without breaking.
            </p>
          </AnimatedSection>

          <div className="flex flex-col gap-24">
            <AnimatedSection delay={0.1}>
              <div className="text-[120px] leading-none font-medium text-white mb-2">12M+</div>
              <div className="text-xl text-[#888]">Total Traces Analyzed</div>
            </AnimatedSection>
            
            <AnimatedSection delay={0.2}>
              <div className="text-[120px] leading-none font-medium text-white mb-2">15+</div>
              <div className="text-xl text-[#888]">Supported Providers</div>
            </AnimatedSection>
            
            <AnimatedSection delay={0.3}>
              <div className="text-[120px] leading-none font-medium text-white mb-2">&lt;35ms</div>
              <div className="text-xl text-[#888]">Policy Verification Time</div>
            </AnimatedSection>
          </div>
        </div>

        {/* Striped border pattern bottom */}
        <div className="absolute bottom-0 left-0 w-full h-8 flex">
           {Array.from({length: 40}).map((_, i) => (
             <div key={i} className={`flex-1 h-full ${i % 2 === 0 ? 'bg-[#111]' : 'bg-[#dcf6cc]'}`} />
           ))}
        </div>
      </section>
    </div>
  );
}
