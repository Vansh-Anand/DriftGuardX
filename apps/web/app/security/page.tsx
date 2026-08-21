"use client"
import React, { useState, useEffect } from "react";
import { ShieldCheck, Lock, Activity, Database, AlertOctagon, Terminal, Server, Key, ShieldAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export default function SecurityDashboard() {
  const [activeTab, setActiveTab] = useState<"verifier" | "isolation" | "dag" | "replay">("verifier");
  const [adversarialInput, setAdversarialInput] = useState("b ａ d ｗ ｏ r ｄ");
  
  // Animation state for replay
  const [replayProgress, setReplayProgress] = useState(0);
  const [replayStatus, setReplayStatus] = useState<"running" | "timeout" | "memory_exceeded">("running");

  useEffect(() => {
    if (activeTab === "replay") {
      setReplayProgress(0);
      setReplayStatus("running");
      const interval = setInterval(() => {
        setReplayProgress(p => {
          if (p >= 30) {
            clearInterval(interval);
            setReplayStatus("timeout");
            return 30.0;
          }
          return p + 0.5;
        });
      }, 50);
      return () => clearInterval(interval);
    }
  }, [activeTab]);

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-slate-200 font-sans p-8">
      
      {/* Header */}
      <div className="mb-10 max-w-7xl mx-auto flex justify-between items-end">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <ShieldCheck className="w-8 h-8 text-emerald-400" />
            <h1 className="text-4xl font-bold tracking-tight text-white">Security & Hardening</h1>
          </div>
          <p className="text-slate-400 text-lg max-w-2xl">
            Patent-Ready Defenses: Cryptographic integrity, bounds enforcement, deterministic verification, and cross-tenant memory isolation.
          </p>
        </div>
        <div className="flex gap-2">
          <Badge variant="certified" className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-3 py-1">
            System Hardened
          </Badge>
          <Badge variant="outline" className="border-slate-700 text-slate-400 px-3 py-1">
            v2.0.0-beta
          </Badge>
        </div>
      </div>

      <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-4 gap-8">
        
        {/* Navigation Sidebar */}
        <div className="col-span-1 space-y-2">
          <TabButton 
            active={activeTab === "verifier"} 
            onClick={() => setActiveTab("verifier")}
            icon={<Terminal className="w-5 h-5" />}
            title="Deterministic Verifier"
            subtitle="Adversarial Normalization"
          />
          <TabButton 
            active={activeTab === "isolation"} 
            onClick={() => setActiveTab("isolation")}
            icon={<Server className="w-5 h-5" />}
            title="Provenance Isolation"
            subtitle="Cross-Tenant Guardrails"
          />
          <TabButton 
            active={activeTab === "dag"} 
            onClick={() => setActiveTab("dag")}
            icon={<Database className="w-5 h-5" />}
            title="Merkle Canonicalization"
            subtitle="Cryptographic Integrity"
          />
          <TabButton 
            active={activeTab === "replay"} 
            onClick={() => setActiveTab("replay")}
            icon={<Activity className="w-5 h-5" />}
            title="Replay Bounds"
            subtitle="Resource Exhaustion Limits"
          />
        </div>

        {/* Main Content Area */}
        <div className="col-span-1 lg:col-span-3">
          <div className="bg-[#111111] border border-slate-800 rounded-2xl p-8 shadow-2xl relative overflow-hidden h-[600px] flex flex-col">
            
            {/* Background Glow */}
            <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-blue-500/5 rounded-full blur-[120px] pointer-events-none -translate-y-1/2 translate-x-1/2" />
            
            {activeTab === "verifier" && (
              <div className="h-full flex flex-col relative z-10 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <div className="mb-6">
                  <h2 className="text-2xl font-bold text-white mb-2">Deterministic Security Verifier</h2>
                  <p className="text-slate-400">
                    Raw inputs undergo a strict canonical normalization pipeline (NFKC, homoglyph mapping, whitespace collapsing) before policy evaluation to prevent bypasses.
                  </p>
                </div>
                
                <div className="grid grid-cols-2 gap-8 flex-1">
                  <div className="flex flex-col">
                    <label className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-2">Adversarial Input</label>
                    <textarea 
                      value={adversarialInput}
                      onChange={(e) => setAdversarialInput(e.target.value)}
                      className="bg-black border border-slate-800 rounded-xl p-4 text-red-400 font-mono text-lg flex-1 focus:outline-none focus:border-red-500/50 transition-colors resize-none"
                    />
                    <div className="mt-4 flex gap-2">
                      <Badge className="bg-red-500/10 text-red-400 border border-red-500/20">Cyrillic Homoglyphs</Badge>
                      <Badge className="bg-red-500/10 text-red-400 border border-red-500/20">Fullwidth Chars</Badge>
                    </div>
                  </div>
                  
                  <div className="flex flex-col relative">
                    <label className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-2 flex justify-between">
                      <span>Normalized State (NFKC)</span>
                      <span className="text-emerald-400 flex items-center gap-1"><ShieldCheck className="w-4 h-4"/> Protected</span>
                    </label>
                    <div className="bg-[#0a0a0a] border border-emerald-500/30 rounded-xl p-4 text-emerald-400 font-mono text-lg flex-1 shadow-[0_0_30px_rgba(16,185,129,0.1)] flex items-center justify-center">
                      <span className="opacity-50 blur-[1px] absolute group-hover:blur-none transition-all">
                        {adversarialInput.toLowerCase().replace(/[\s\u3000]+/g, '').replace(/[ａ-ｚ]/g, c => String.fromCharCode(c.charCodeAt(0) - 0xfee0))}
                      </span>
                      <div className="text-center z-10 bg-black/80 px-6 py-4 rounded-xl border border-emerald-500/50 backdrop-blur-md">
                        <ShieldAlert className="w-12 h-12 text-red-500 mx-auto mb-3" />
                        <span className="text-red-400 font-bold block mb-1">POLICY VIOLATION DENIED</span>
                        <span className="text-slate-400 text-sm">Target normalized to forbidden substring</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "isolation" && (
              <div className="h-full flex flex-col relative z-10 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <div className="mb-6">
                  <h2 className="text-2xl font-bold text-white mb-2">Cross-Tenant Provenance Isolation</h2>
                  <p className="text-slate-400">
                    Memory reads and writes are cryptographically hard-bounded to the requesting `tenant_id`, preventing IDOR (Insecure Direct Object Reference) access to quarantined partitions.
                  </p>
                </div>
                
                <div className="flex-1 flex items-center justify-center">
                  <div className="relative w-full max-w-3xl">
                    <div className="absolute top-1/2 left-0 w-full h-0.5 bg-slate-800 -translate-y-1/2 z-0" />
                    
                    <div className="grid grid-cols-3 gap-8 relative z-10">
                      {/* Tenant A Request */}
                      <div className="bg-black border border-slate-700 rounded-xl p-5 shadow-xl">
                        <div className="flex items-center gap-2 mb-3">
                          <div className="w-2 h-2 rounded-full bg-blue-500" />
                          <span className="font-bold text-white">Tenant A</span>
                        </div>
                        <code className="text-xs text-slate-400 block mb-1">req.tenant_id = "T_111"</code>
                        <code className="text-xs text-blue-400 block mb-3">read("partition:T_222_data")</code>
                        <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-xs py-1.5 px-2 rounded font-mono text-center">
                          DENIED: Tenant Mismatch
                        </div>
                      </div>

                      {/* Firewall Boundary */}
                      <div className="flex flex-col items-center justify-center">
                        <div className="w-16 h-16 rounded-2xl bg-[#111] border-2 border-emerald-500/50 shadow-[0_0_30px_rgba(16,185,129,0.2)] flex items-center justify-center relative overflow-hidden">
                          <div className="absolute inset-0 bg-emerald-500/10 animate-pulse" />
                          <Lock className="w-6 h-6 text-emerald-400 relative z-10" />
                        </div>
                        <span className="text-xs font-bold text-emerald-500 mt-3 uppercase tracking-widest">Enforcement Boundary</span>
                      </div>

                      {/* Tenant B Data */}
                      <div className="bg-black border border-emerald-500/30 rounded-xl p-5 shadow-xl opacity-80">
                        <div className="flex items-center gap-2 mb-3">
                          <div className="w-2 h-2 rounded-full bg-emerald-500" />
                          <span className="font-bold text-white">Tenant B Partition</span>
                        </div>
                        <code className="text-xs text-slate-400 block mb-1">owner_id = "T_222"</code>
                        <code className="text-xs text-emerald-400 block mb-3">status = "QUARANTINED"</code>
                        <div className="bg-slate-900 border border-slate-700 text-slate-500 text-xs py-1.5 px-2 rounded font-mono text-center">
                          Data Secure
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "dag" && (
              <div className="h-full flex flex-col relative z-10 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <div className="mb-6">
                  <h2 className="text-2xl font-bold text-white mb-2">DAG Cryptographic Canonicalization</h2>
                  <p className="text-slate-400">
                    Domain-separated deterministic hashing (`0x00` for leaves, `0x01` for internal nodes) prevents hash collisions and graph cycle injection attacks that existed in the raw `str(dict)` approach.
                  </p>
                </div>
                
                <div className="flex-1 grid grid-cols-2 gap-8 items-center">
                  <div className="bg-red-950/20 border border-red-900/50 rounded-xl p-6">
                     <h3 className="text-red-400 font-bold mb-4 flex items-center gap-2"><AlertOctagon className="w-5 h-5"/> Legacy Vulnerability</h3>
                     <code className="block bg-black p-3 rounded border border-red-900/30 text-xs text-red-300 mb-4 font-mono">
                       hash = SHA256(str(dict_payload))
                     </code>
                     <ul className="text-sm text-red-400/80 space-y-2 list-disc list-inside">
                       <li>Order dependent keys cause hash mismatch</li>
                       <li>No separation between leaves and branches</li>
                       <li>Vulnerable to cycle-pollution DoS</li>
                     </ul>
                  </div>

                  <div className="bg-emerald-950/20 border border-emerald-900/50 rounded-xl p-6 relative overflow-hidden">
                     <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/10 rounded-full blur-[40px]" />
                     <h3 className="text-emerald-400 font-bold mb-4 flex items-center gap-2"><Key className="w-5 h-5"/> Domain Separated</h3>
                     <code className="block bg-black p-3 rounded border border-emerald-900/50 text-xs text-emerald-300 mb-2 font-mono">
                       payload = json_dumps(canonical_dict)
                     </code>
                     <code className="block bg-black p-3 rounded border border-emerald-900/50 text-xs text-emerald-300 mb-4 font-mono">
                       hash = SHA256(0x01 || payload)
                     </code>
                     <ul className="text-sm text-emerald-400/80 space-y-2 list-disc list-inside">
                       <li>Deterministic JSON serialization</li>
                       <li>Domain prefixes separate node types</li>
                       <li>Buffer-based cycle detection</li>
                     </ul>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "replay" && (
              <div className="h-full flex flex-col relative z-10 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <div className="mb-6">
                  <h2 className="text-2xl font-bold text-white mb-2">Counterfactual Replay Bounds</h2>
                  <p className="text-slate-400">
                    The Counterfactual Replay Engine now wraps component execution in a strict thread pool with hard timeouts (30.0s) and payload size limits (5MB) to prevent adversarial resource exhaustion during simulation.
                  </p>
                </div>
                
                <div className="flex-1 flex flex-col justify-center max-w-2xl mx-auto w-full">
                  
                  <div className="bg-black border border-slate-800 rounded-xl p-6 shadow-2xl relative overflow-hidden">
                    <div className="flex justify-between items-center mb-6">
                      <span className="font-mono text-sm text-blue-400">Replay Thread Pool (1 Worker)</span>
                      <Badge variant="outline" className={replayStatus === 'running' ? 'border-blue-500 text-blue-400' : 'border-red-500 text-red-400'}>
                        {replayStatus === 'running' ? 'EXECUTING' : 'TERMINATED'}
                      </Badge>
                    </div>

                    <div className="space-y-6">
                      {/* Timeout Meter */}
                      <div>
                        <div className="flex justify-between text-xs text-slate-500 font-bold uppercase tracking-wider mb-2">
                          <span>Execution Time</span>
                          <span className={replayProgress >= 30 ? 'text-red-400' : ''}>{replayProgress.toFixed(1)}s / 30.0s Limit</span>
                        </div>
                        <div className="h-3 w-full bg-slate-900 rounded-full overflow-hidden border border-slate-800">
                          <div 
                            className={`h-full transition-all duration-75 ${replayProgress >= 30 ? 'bg-red-500' : 'bg-blue-500'}`}
                            style={{ width: `${(replayProgress / 30) * 100}%` }}
                          />
                        </div>
                      </div>

                      {/* Log output */}
                      <div className="bg-[#0a0a0a] rounded-lg p-4 font-mono text-xs text-slate-400 border border-slate-800 h-32 overflow-y-auto">
                        <div className="text-slate-500">[0.0s] Initiating counterfactual replay...</div>
                        <div className="text-slate-500">[0.1s] Bound execution environment started.</div>
                        <div className="text-slate-500">[0.2s] Simulating adversarial component halt...</div>
                        {replayProgress > 5 && <div className="text-yellow-500/70">[5.0s] Component execution stalling...</div>}
                        {replayProgress > 15 && <div className="text-yellow-500/70">[15.0s] Awaiting response...</div>}
                        {replayProgress > 25 && <div className="text-orange-500/70">[25.0s] Approaching critical bounds...</div>}
                        {replayStatus === 'timeout' && (
                          <div className="text-red-400 font-bold mt-2">
                            [30.0s] CRITICAL: concurrent.futures.TimeoutError<br/>
                            Execution exceeded hard timeout limit (30.0s). Thread forcefully terminated to prevent resource exhaustion.
                          </div>
                        )}
                      </div>
                    </div>
                    
                    {replayStatus !== 'running' && (
                      <button 
                        onClick={() => setActiveTab('replay')} 
                        className="absolute bottom-4 right-6 text-xs text-blue-400 hover:text-blue-300 font-semibold"
                      >
                        RESTART SIMULATION
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}

function TabButton({ active, onClick, icon, title, subtitle }: any) {
  return (
    <button 
      onClick={onClick}
      className={`w-full text-left p-4 rounded-xl transition-all duration-300 flex items-center gap-4 ${
        active 
          ? "bg-slate-800/50 border border-slate-700 shadow-md" 
          : "bg-transparent border border-transparent hover:bg-slate-900/50 text-slate-500 hover:text-slate-300"
      }`}
    >
      <div className={`p-2 rounded-lg ${active ? "bg-blue-500/20 text-blue-400" : "bg-slate-900 text-slate-600"}`}>
        {icon}
      </div>
      <div>
        <div className={`font-bold ${active ? "text-white" : ""}`}>{title}</div>
        <div className={`text-xs ${active ? "text-slate-400" : "text-slate-600"}`}>{subtitle}</div>
      </div>
    </button>
  );
}
