"use client"
import React, { useState } from "react";

// ─── Mock Data ────────────────────────────────────────────────────────────────
const MOCK_RATIONALES = [
  {
    id: "rat_1",
    style: "OPERATOR_SUMMARY",
    content: "[Diagnosis] Root cause localized to component `retriever` (Path: api -> retriever).\n[Evidence] Replay Episode `rep_123` shifted version `v1.0` to `v1.1`, yielding metric deltas: quality: +0.05, latency: -10.0.\n[Policy] Status is CERTIFIED (Bound: hoeffding, epsilon=0.1, delta=0.01). Decision: `APPROVED`. Action triggered: `ROLLBACK`.\n[Limitations] Assumes independent queries",
    is_llm_generated: false,
    fallback_triggered: true,
  },
  {
    id: "rat_2",
    style: "EXECUTIVE_SUMMARY",
    content: "The LLM analyzed the issue in retriever. Switching v1.0 to v1.1 caused metric shifts. (Mock generated text)",
    is_llm_generated: true,
    fallback_triggered: false,
    factual_consistency_score: 1.0,
    model_version: "gpt-4o",
    latency_ms: 450.2
  }
];

// Highlight component that wraps recognized tags
const RationaleText = ({ text }: { text: string }) => {
  // Split on words like `retriever`, `v1.0`, or [Tags] to make them look cited.
  // In a real app, this would use exact span pointers.
  const parts = text.split(/(`[^`]+`|\[[^\]]+\])/g);
  
  return (
    <div className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">
      {parts.map((part, i) => {
        if (part.startsWith('`') && part.endsWith('`')) {
          return (
            <span key={i} className="cursor-help bg-blue-50 text-blue-700 px-1 py-0.5 rounded border border-blue-100 font-mono text-xs mx-0.5 relative group">
              {part.slice(1, -1)}
              {/* Tooltip simulating cited evidence */}
              <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block w-max max-w-xs bg-slate-900 text-white text-xs p-2 rounded shadow-lg z-10 text-center">
                Cited from Evidence Input
              </span>
            </span>
          );
        }
        if (part.startsWith('[') && part.endsWith(']')) {
          return (
            <strong key={i} className="text-slate-900 font-bold">
              {part}
            </strong>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </div>
  );
};


export default function RationaleViewer() {
  const [selectedStyle, setSelectedStyle] = useState("OPERATOR_SUMMARY");
  
  const current = MOCK_RATIONALES.find(r => r.style === selectedStyle) || MOCK_RATIONALES[0];

  return (
    <div className="min-h-screen bg-slate-50 font-sans pb-12">
      {/* Header */}
      <header className="bg-slate-900 text-white px-8 py-5 flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">Recovery Rationale</h1>
          <p className="text-slate-400 text-sm mt-1">
            Grounded Natural-Language Generation with Hallucination Controls
          </p>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-8 py-8 space-y-6">
        
        {/* Style Selector */}
        <div className="flex gap-2">
          {["OPERATOR_SUMMARY", "EXECUTIVE_SUMMARY", "INCIDENT_TICKET", "PATENT_NOTE"].map(style => (
            <button
              key={style}
              onClick={() => setSelectedStyle(style)}
              className={`px-4 py-2 text-sm font-bold rounded shadow-sm border transition-colors ${
                selectedStyle === style 
                  ? "bg-indigo-600 text-white border-indigo-700" 
                  : "bg-white text-slate-700 hover:bg-slate-50 border-slate-200"
              }`}
            >
              {style.replace("_", " ")}
            </button>
          ))}
        </div>

        {/* Output Card */}
        <div className="bg-white rounded-lg border shadow-sm p-6 relative overflow-hidden">
          {/* Generation Meta */}
          <div className="flex justify-between items-center border-b pb-4 mb-4">
            <div className="flex items-center gap-3">
              {current.is_llm_generated ? (
                <span className="px-2 py-1 bg-purple-100 text-purple-800 text-xs font-bold rounded border border-purple-200">
                  LLM GENERATED
                </span>
              ) : (
                <span className="px-2 py-1 bg-amber-100 text-amber-800 text-xs font-bold rounded border border-amber-200">
                  TEMPLATE FALLBACK
                </span>
              )}
              {current.factual_consistency_score !== undefined && (
                <span className="text-xs text-slate-500 font-mono">
                  Fact Score: {(current.factual_consistency_score * 100).toFixed(0)}%
                </span>
              )}
            </div>
            {current.model_version && (
              <div className="text-xs text-slate-400 font-mono">
                Model: {current.model_version} | Latency: {current.latency_ms?.toFixed(1)}ms
              </div>
            )}
          </div>

          {/* Rendered Text */}
          <RationaleText text={current.content} />
          
        </div>
      </main>
    </div>
  );
}
