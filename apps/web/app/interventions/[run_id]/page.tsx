"use client"
import React from 'react';

const MOCK_RESULTS = {
  run_id: "r_123456",
  optimal: [
    {
      id: "ep_opt_1",
      intervention_type: "ROLLBACK",
      target_component: "retriever",
      original_score: 0.75,
      replay_score: 0.92,
      cost_delta: +0.01,
      latency_delta: +10,
    }
  ],
  dominated: [
    {
      id: "ep_dom_1",
      intervention_type: "ALTERNATE_STABLE",
      target_component: "generator",
      original_score: 0.75,
      replay_score: 0.80, // Lower score improvement than optimal
      cost_delta: +0.05,
      latency_delta: +500,
    }
  ],
  invalid: [
    {
      id: "ep_inv_1",
      intervention_type: "CONFIG_PATCH",
      target_component: "retriever",
      reason: "Missing Artifact"
    }
  ]
};

export default function InterventionReviewPage({ params }: { params: { run_id: string } }) {
  return (
    <div className="p-8 max-w-6xl mx-auto font-sans">
      <header className="mb-8 border-b pb-4 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold mb-2">Intervention Planner</h1>
          <p className="text-gray-600">Run ID: {params.run_id}</p>
        </div>
        <button className="bg-blue-600 text-white px-4 py-2 rounded font-medium hover:bg-blue-700">
          Approve Optimal Strategy
        </button>
      </header>

      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4 flex items-center gap-2">
          <span className="bg-green-100 text-green-800 text-sm px-2 py-1 rounded">Optimal</span>
          Pareto Frontier
        </h2>
        <div className="bg-white border-2 border-green-200 rounded-lg shadow-sm">
          {MOCK_RESULTS.optimal.map((ep) => (
            <div key={ep.id} className="p-4 flex justify-between items-center border-b last:border-0">
              <div>
                <h3 className="font-bold text-lg capitalize">{ep.intervention_type.replace('_', ' ')}</h3>
                <p className="text-gray-600 text-sm">Target: <span className="font-mono bg-gray-100 px-1">{ep.target_component}</span></p>
              </div>
              <div className="text-right">
                <div className="text-xl font-bold text-green-600">+{((ep.replay_score - ep.original_score)*100).toFixed(0)}% Score</div>
                <div className="text-xs text-gray-500">Latency: {ep.latency_delta > 0 ? '+' : ''}{ep.latency_delta}ms | Cost: +${ep.cost_delta}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4 flex items-center gap-2">
          <span className="bg-yellow-100 text-yellow-800 text-sm px-2 py-1 rounded">Negative</span>
          Dominated Alternatives
        </h2>
        <div className="bg-white border rounded-lg shadow-sm">
          {MOCK_RESULTS.dominated.map((ep) => (
            <div key={ep.id} className="p-4 flex justify-between items-center border-b last:border-0">
              <div>
                <h3 className="font-bold text-lg capitalize text-gray-700">{ep.intervention_type.replace('_', ' ')}</h3>
                <p className="text-gray-500 text-sm">Target: <span className="font-mono bg-gray-50 px-1">{ep.target_component}</span></p>
              </div>
              <div className="text-right opacity-75">
                <div className="text-lg font-semibold text-yellow-600">+{((ep.replay_score - ep.original_score)*100).toFixed(0)}% Score</div>
                <div className="text-xs text-gray-400">Latency: {ep.latency_delta > 0 ? '+' : ''}{ep.latency_delta}ms | Cost: +${ep.cost_delta}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-4 flex items-center gap-2">
          <span className="bg-red-100 text-red-800 text-sm px-2 py-1 rounded">Invalid</span>
          Rejected Candidates
        </h2>
        <div className="bg-gray-50 border rounded-lg shadow-sm text-gray-600">
          {MOCK_RESULTS.invalid.map((ep) => (
            <div key={ep.id} className="p-4 flex justify-between items-center border-b last:border-0">
              <div>
                <h3 className="font-medium capitalize">{ep.intervention_type.replace('_', ' ')}</h3>
                <p className="text-sm">Target: <span className="font-mono">{ep.target_component}</span></p>
              </div>
              <div className="text-right">
                <div className="text-sm font-semibold bg-red-50 text-red-700 px-2 py-1 rounded border border-red-100">
                  {ep.reason}
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
