'use client';
import { PageLayout } from '@/components/PageLayout';
import React from 'react';
import { Clock, AlertTriangle } from 'lucide-react';

const MOCK_SYMPTOMS = [
  {
    id: "sym_1",
    detected_at: "2026-07-22T08:12:00Z",
    symptom_name: "retrieval_drift_detector.top_k_overlap",
    severity: "high",
    is_anomaly: true,
    graph_node_id: "retriever:span_abc123",
    evidence_snippet: "Overlap score 0.3 < 0.5 threshold",
    false_positive: false,
    layer: "Retrieval"
  },
  {
    id: "sym_2",
    detected_at: "2026-07-22T08:12:05Z",
    symptom_name: "generation_drift_detector.unsupported_claim_rate",
    severity: "high",
    is_anomaly: true,
    graph_node_id: "generator:span_xyz789",
    evidence_snippet: "Unsupported claims 0.15 > 0.10 threshold",
    false_positive: false,
    layer: "Generation"
  },
  {
    id: "sym_3",
    detected_at: "2026-07-22T08:15:22Z",
    symptom_name: "policy_drift_detector.unexpected_allow_rate",
    severity: "low",
    is_anomaly: true,
    graph_node_id: "policy:span_def456",
    evidence_snippet: "Unexpected allow rate 0.02 > 0.01 threshold",
    false_positive: true,
    layer: "Policy"
  }
];

export default function TimelinePage() {
  const badge = (
    <span className="font-mono text-[10px] border border-[#0a0a0a] px-3 py-1.5 uppercase tracking-widest">
      {MOCK_SYMPTOMS.length} Events
    </span>
  );

  return (
    <PageLayout title="Drift Timeline" subtitle="Versioned execution spans and anomaly detection events" badge={badge}>
      <div className="p-8">
        {/* Legend */}
        <div className="flex gap-8 mb-8 border-b border-[#0a0a0a]/10 pb-4">
          <span className="font-mono text-[10px] uppercase tracking-widest text-[#888] flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-[#0a0a0a] inline-block"/>Anomaly
          </span>
          <span className="font-mono text-[10px] uppercase tracking-widest text-[#888] flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-[#888] inline-block border border-[#0a0a0a]"/>False Positive
          </span>
        </div>

        {/* Timeline */}
        <div className="relative border-l border-[#0a0a0a] ml-4 space-y-0">
          {MOCK_SYMPTOMS.map((sym, i) => (
            <div key={sym.id} className={`relative pl-10 pb-8 ${i < MOCK_SYMPTOMS.length - 1 ? '' : ''}`}>
              {/* Dot */}
              <div className={`absolute -left-2 top-1 w-4 h-4 border border-[#0a0a0a] flex items-center justify-center ${sym.false_positive ? 'bg-[#888]' : 'bg-[#0a0a0a]'}`}>
                <span className="text-[6px] text-[#ECEAE2]">{sym.false_positive ? '?' : '!'}</span>
              </div>

              {/* Card */}
              <div className={`border ${sym.false_positive ? 'border-[#888]' : 'border-[#0a0a0a]'} p-5`}>
                <div className="flex justify-between items-start mb-3">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-[10px] border border-[#0a0a0a] px-2 py-0.5 uppercase tracking-wider">{sym.layer}</span>
                    <span className={`font-mono text-[10px] border px-2 py-0.5 uppercase tracking-wider ${sym.severity === 'high' ? 'border-red-500 text-red-600' : 'border-[#888] text-[#888]'}`}>
                      {sym.severity}
                    </span>
                  </div>
                  <span className="font-mono text-[10px] text-[#888]">
                    {new Date(sym.detected_at).toLocaleTimeString()}
                  </span>
                </div>

                <h3 className="font-mono text-xs font-bold text-[#0a0a0a] mb-3">{sym.symptom_name}</h3>

                <div className="font-mono text-xs text-[#888] bg-[#0a0a0a]/5 border border-[#0a0a0a]/10 px-3 py-2 mb-3">
                  {sym.evidence_snippet}
                </div>

                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] text-[#888]">
                    Node: <code className="text-[#0a0a0a] bg-[#0a0a0a]/10 px-1">{sym.graph_node_id}</code>
                  </span>
                  {sym.false_positive && (
                    <span className="font-mono text-[10px] text-[#888] flex items-center gap-1 border border-[#888] px-2 py-0.5">
                      <AlertTriangle className="w-3 h-3" /> Retained False Positive
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </PageLayout>
  );
}
