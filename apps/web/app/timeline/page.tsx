import React from 'react';
import { Clock, AlertTriangle, ShieldAlert } from 'lucide-react';

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
  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-3xl font-bold tracking-tight text-gray-900 flex items-center gap-3">
            <Clock className="w-8 h-8 text-blue-600" />
            Drift Timeline
          </h1>
          <div className="flex gap-4 text-sm font-medium">
            <span className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-red-500"></span> Anomaly
            </span>
            <span className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-yellow-400"></span> False Positive
            </span>
          </div>
        </div>
        
        <div className="relative border-l-2 border-gray-200 ml-4 space-y-8">
          {MOCK_SYMPTOMS.map((sym) => (
            <div key={sym.id} className="relative pl-8">
              <div className={`absolute -left-2.5 top-1.5 w-5 h-5 rounded-full border-4 border-white flex items-center justify-center ${sym.false_positive ? 'bg-yellow-400' : 'bg-red-500'}`}>
              </div>
              
              <div className={`bg-white rounded-xl shadow-sm border p-5 ${sym.false_positive ? 'border-yellow-200' : 'border-red-100'}`}>
                <div className="flex justify-between items-start mb-3">
                  <div className="flex items-center gap-3">
                    <span className="inline-flex items-center rounded-md bg-gray-100 px-2.5 py-0.5 text-xs font-semibold text-gray-600">
                      {sym.layer}
                    </span>
                    <h3 className="text-lg font-semibold text-gray-900">
                      {sym.symptom_name}
                    </h3>
                  </div>
                  <span className="text-xs text-gray-500">
                    {new Date(sym.detected_at).toLocaleTimeString()}
                  </span>
                </div>
                
                <p className="text-sm text-gray-700 mb-3 font-mono bg-gray-50 p-2 rounded border border-gray-100">
                  {sym.evidence_snippet}
                </p>
                
                <div className="flex items-center justify-between text-xs text-gray-500">
                  <span>Node: <code className="text-blue-600 bg-blue-50 px-1 py-0.5 rounded">{sym.graph_node_id}</code></span>
                  {sym.false_positive && (
                    <span className="flex items-center gap-1 text-yellow-700 font-medium bg-yellow-50 px-2 py-1 rounded-full">
                      <AlertTriangle className="w-3 h-3" />
                      Retained False Positive
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
