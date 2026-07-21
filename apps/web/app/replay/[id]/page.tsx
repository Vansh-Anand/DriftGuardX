"use client"
import React, { useState } from 'react';

// Mock data for the replay UI
const MOCK_REPLAY = {
  id: "e9f81d11-b12a-4a2b-81d1-12a4a2b81d11",
  capsule_hash: "abcd1234efgh5678",
  status: "COMPLETED",
  intervened_component: {
    type: "retriever",
    original_version: "v1.2",
    replay_version: "v2.0"
  },
  metrics: {
    faithfulness: { original: 0.85, replay: 0.95, delta: 0.1 },
    task_success: { original: 0.70, replay: 0.90, delta: 0.2 },
    latency_ms: { original: 1200, replay: 1100, delta: -100 }
  },
  freeze_invariants_valid: true
};

export default function ReplayComparisonPage({ params }: { params: { id: string } }) {
  const [activeTab, setActiveTab] = useState<'metrics' | 'traces' | 'logs'>('metrics');

  if (!MOCK_REPLAY) return <div>Loading replay...</div>;

  return (
    <div className="p-8 max-w-6xl mx-auto font-sans">
      <header className="mb-8 border-b pb-4">
        <h1 className="text-3xl font-bold mb-2">Replay Explorer: {params.id}</h1>
        <div className="flex gap-4 text-sm text-gray-600">
          <span className="bg-gray-100 px-2 py-1 rounded">Capsule: {MOCK_REPLAY.capsule_hash}</span>
          <span className={`px-2 py-1 rounded text-white ${MOCK_REPLAY.status === 'COMPLETED' ? 'bg-green-600' : 'bg-yellow-600'}`}>
            {MOCK_REPLAY.status}
          </span>
          {MOCK_REPLAY.freeze_invariants_valid ? (
             <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded border border-blue-200">✓ Freeze Invariants Verified</span>
          ) : (
             <span className="bg-red-100 text-red-800 px-2 py-1 rounded border border-red-200">⚠ Sandbox Violation Detected</span>
          )}
        </div>
      </header>

      <div className="grid grid-cols-3 gap-6 mb-8">
        <div className="col-span-1 bg-white p-6 rounded-lg shadow border">
          <h2 className="text-xl font-semibold mb-4">Intervention</h2>
          <div className="flex flex-col gap-2">
            <div>
              <span className="text-gray-500 text-sm block">Component</span>
              <span className="font-medium capitalize">{MOCK_REPLAY.intervened_component.type}</span>
            </div>
            <div className="flex items-center gap-2 mt-2">
              <div className="bg-red-50 text-red-700 px-3 py-2 rounded flex-1 text-center border border-red-100">
                {MOCK_REPLAY.intervened_component.original_version}
              </div>
              <span className="text-gray-400">→</span>
              <div className="bg-green-50 text-green-700 px-3 py-2 rounded flex-1 text-center border border-green-100">
                {MOCK_REPLAY.intervened_component.replay_version}
              </div>
            </div>
          </div>
        </div>

        <div className="col-span-2 bg-white p-6 rounded-lg shadow border">
          <h2 className="text-xl font-semibold mb-4">Reliability Delta</h2>
          <div className="grid grid-cols-3 gap-4">
            {Object.entries(MOCK_REPLAY.metrics).map(([metric, values]) => (
              <div key={metric} className="flex flex-col">
                <span className="text-gray-500 text-sm capitalize">{metric.replace('_', ' ')}</span>
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-bold">{values.replay}</span>
                  <span className={`text-sm font-medium ${values.delta > 0 ? 'text-green-600' : values.delta < 0 ? 'text-red-600' : 'text-gray-400'}`}>
                    {values.delta > 0 ? '+' : ''}{values.delta}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      
      <div className="mt-8 border rounded-lg overflow-hidden">
        <div className="flex border-b bg-gray-50">
          <button 
            className={`px-6 py-3 font-medium ${activeTab === 'metrics' ? 'border-b-2 border-blue-600 text-blue-600' : 'text-gray-600 hover:bg-gray-100'}`}
            onClick={() => setActiveTab('metrics')}
          >
            Metrics Breakdown
          </button>
          <button 
            className={`px-6 py-3 font-medium ${activeTab === 'traces' ? 'border-b-2 border-blue-600 text-blue-600' : 'text-gray-600 hover:bg-gray-100'}`}
            onClick={() => setActiveTab('traces')}
          >
            Trace Comparison
          </button>
        </div>
        
        <div className="p-6 bg-white min-h-[400px]">
          {activeTab === 'metrics' && (
            <div>
              <p className="text-gray-600">Metric evaluation logs and confidence intervals will appear here.</p>
            </div>
          )}
          {activeTab === 'traces' && (
            <div className="grid grid-cols-2 gap-4">
              <div className="border rounded p-4">
                <h3 className="font-semibold mb-2">Original Execution</h3>
                <pre className="text-xs bg-gray-50 p-2 rounded text-gray-800">
                  {"[Retrieval] Found 2 documents\n[Generation] The answer is X."}
                </pre>
              </div>
              <div className="border rounded p-4">
                <h3 className="font-semibold mb-2 flex items-center justify-between">
                  Replay Execution
                  <span className="text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded">Modified</span>
                </h3>
                <pre className="text-xs bg-green-50 border border-green-100 p-2 rounded text-gray-800">
                  {"[Retrieval] Found 5 documents (updated)\n[Generation] The answer is Y based on more context."}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
