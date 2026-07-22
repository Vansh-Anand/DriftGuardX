"use client"
import React from 'react';

const MOCK_REPORT = {
  run_id: "r_987654321",
  abstention_triggered: false,
  limitations: [
    "Learned attribution only. Does not imply causal proof beyond exhaustive replay bounds.",
    "Cost constraints limited repeated trials to N=3."
  ],
  recommended_next_step: "Approve Rollback of Retriever to v1.",
  ranked_candidates: [
    {
      id: "rc_1",
      component_type: "retriever",
      intervention_type: "ROLLBACK",
      aggregate_score: 8.5,
      reliability_improvement_mean: +0.10,
      reliability_improvement_variance: 0.0001,
      cost_delta_usd: 0.01,
      latency_delta_ms: 10.0,
      invalid_rate: 0.0,
      trials_n: 3,
      is_negative_control: false
    },
    {
      id: "rc_2",
      component_type: "generator",
      intervention_type: "NO_OP",
      aggregate_score: 0.0,
      reliability_improvement_mean: +0.001,
      reliability_improvement_variance: 0.0005,
      cost_delta_usd: 0.0,
      latency_delta_ms: 0.0,
      invalid_rate: 0.0,
      trials_n: 3,
      is_negative_control: true
    },
    {
      id: "rc_3",
      component_type: "policy_check",
      intervention_type: "DISABLE",
      aggregate_score: 0.0,
      reliability_improvement_mean: -0.05,
      reliability_improvement_variance: 0.001,
      cost_delta_usd: 0.0,
      latency_delta_ms: -50.0, // Faster, but accuracy dropped heavily
      invalid_rate: 0.33,
      trials_n: 3,
      is_negative_control: false
    }
  ]
};

export default function RootCauseReportPage({ params }: { params: { run_id: string } }) {
  return (
    <div className="p-8 max-w-6xl mx-auto font-sans bg-gray-50 min-h-screen">
      <header className="mb-8 border-b pb-4">
        <h1 className="text-3xl font-bold mb-2 text-indigo-900">Certified Root Cause Diagnosis</h1>
        <p className="text-gray-600 font-mono text-sm">Run: {params.run_id}</p>
      </header>

      {/* Causal Language Disclaimer */}
      <section className="mb-6 bg-blue-50 border-l-4 border-blue-500 p-4 rounded text-sm text-blue-900">
        <h3 className="font-bold mb-1">Causal Evidence Limitations</h3>
        <ul className="list-disc ml-5 space-y-1">
          {MOCK_REPORT.limitations.map((limit, i) => (
            <li key={i}>{limit}</li>
          ))}
        </ul>
        <p className="mt-2 text-xs italic">
          * Terms such as "likely root cause" represent strong correlative improvement during exhaustive replay, 
          not an absolute mathematical proof of counterfactual necessity.
        </p>
      </section>

      {/* Main Report Table */}
      <section className="bg-white rounded-lg shadow-sm border p-6 mb-8">
        <h2 className="text-xl font-semibold mb-4">Ranked Candidates</h2>
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b text-gray-500 text-sm">
              <th className="py-2">Rank</th>
              <th className="py-2">Component</th>
              <th className="py-2">Intervention</th>
              <th className="py-2">Reliability Gain (Mean ± Var)</th>
              <th className="py-2">Cost Delta</th>
              <th className="py-2">Latency Delta</th>
              <th className="py-2">Agg. Score</th>
            </tr>
          </thead>
          <tbody>
            {MOCK_REPORT.ranked_candidates.map((c, i) => (
              <tr key={c.id} className={`border-b last:border-0 ${c.is_negative_control ? 'bg-gray-50 opacity-75' : ''}`}>
                <td className="py-3 px-2 font-bold text-gray-700">{i + 1}</td>
                <td className="py-3 px-2 font-mono text-sm">{c.component_type}</td>
                <td className="py-3 px-2">
                  <span className="capitalize">{c.intervention_type.replace('_', ' ')}</span>
                  {c.is_negative_control && <span className="ml-2 text-xs bg-gray-200 px-1 rounded">Control</span>}
                </td>
                <td className="py-3 px-2">
                  <span className={c.reliability_improvement_mean > 0 ? 'text-green-600 font-medium' : 'text-red-500 font-medium'}>
                    {c.reliability_improvement_mean > 0 ? '+' : ''}{(c.reliability_improvement_mean * 100).toFixed(1)}%
                  </span>
                  <span className="text-xs text-gray-400 ml-1">±{c.reliability_improvement_variance.toFixed(4)}</span>
                  <div className="text-xs text-gray-400">N={c.trials_n}</div>
                </td>
                <td className="py-3 px-2 text-sm">${c.cost_delta_usd}</td>
                <td className="py-3 px-2 text-sm">{c.latency_delta_ms}ms</td>
                <td className="py-3 px-2 font-bold text-indigo-600">{c.aggregate_score.toFixed(1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* Abstention & Next Steps */}
      <section className="bg-white rounded-lg shadow-sm border p-6 border-t-4 border-t-green-500">
        <h2 className="text-lg font-bold mb-2">Diagnostic Conclusion</h2>
        {MOCK_REPORT.abstention_triggered ? (
          <p className="text-gray-700">
            <strong className="text-red-600">Abstention Triggered:</strong> Insufficient evidence to confidently recommend an intervention. No candidate produced a material, policy-relevant improvement above the 5% threshold.
          </p>
        ) : (
          <div>
            <p className="text-gray-700 mb-4">
              A likely recoverable root cause has been identified.
            </p>
            <div className="bg-green-50 border border-green-200 text-green-900 p-4 rounded flex items-center justify-between">
              <div>
                <span className="block text-sm font-bold text-green-700 mb-1">Recommended Action</span>
                <span>{MOCK_REPORT.recommended_next_step}</span>
              </div>
              <button className="bg-green-600 text-white px-6 py-2 rounded font-medium hover:bg-green-700">
                Execute Action
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
