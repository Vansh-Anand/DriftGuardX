"use client"
import React from 'react';

const MOCK_BANDIT_STATE = {
  run_id: "r_bandit_123",
  total_budget: 1.00,
  remaining_budget: 0.15,
  total_pulls: 59,
  stop_reason: "Confidence Reached",
  arms: [
    { id: "arm_root_cause", component: "retriever", prior: 0.5, pulls: 35, expected_reward: 0.85, ucb: 0.92, cost: 0.05 },
    { id: "arm_distractor", component: "generator", prior: 0.9, pulls: 22, expected_reward: 0.15, ucb: 0.28, cost: 0.01 },
    { id: "arm_expensive", component: "policy", prior: 0.2, pulls: 2, expected_reward: 0.40, ucb: 0.95, cost: 0.50 }
  ]
};

export default function SchedulerInspectionPage({ params }: { params: { run_id: string } }) {
  const percentUsed = ((MOCK_BANDIT_STATE.total_budget - MOCK_BANDIT_STATE.remaining_budget) / MOCK_BANDIT_STATE.total_budget) * 100;
  
  return (
    <div className="p-8 max-w-6xl mx-auto font-sans bg-slate-50 min-h-screen">
      <header className="mb-8 border-b pb-4 flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold mb-2 text-slate-800">BCRB Scheduler Inspection</h1>
          <p className="text-slate-600 font-mono text-sm">Run: {params.run_id}</p>
        </div>
        <div className="text-right">
          <div className="text-xs uppercase font-bold text-slate-500 mb-1">Status</div>
          <div className="bg-green-100 text-green-800 px-3 py-1 rounded font-semibold">
            {MOCK_BANDIT_STATE.stop_reason}
          </div>
        </div>
      </header>

      {/* Budget Tracker */}
      <section className="mb-8 bg-white p-6 rounded-lg shadow-sm border">
        <h2 className="text-xl font-semibold mb-4">Budget Ledger</h2>
        <div className="flex items-center justify-between mb-2">
          <span className="font-medium text-slate-700">Budget Spent</span>
          <span className="font-mono">${(MOCK_BANDIT_STATE.total_budget - MOCK_BANDIT_STATE.remaining_budget).toFixed(2)} / ${MOCK_BANDIT_STATE.total_budget.toFixed(2)}</span>
        </div>
        <div className="w-full bg-slate-200 rounded-full h-4">
          <div className="bg-indigo-600 h-4 rounded-full" style={{ width: `${percentUsed}%` }}></div>
        </div>
        <div className="mt-4 text-sm text-slate-500 text-right">
          Total Replay Pulls: {MOCK_BANDIT_STATE.total_pulls}
        </div>
      </section>

      {/* Arm Ledger */}
      <section className="bg-white p-6 rounded-lg shadow-sm border">
        <h2 className="text-xl font-semibold mb-4">Arm Exploration & Exploitation</h2>
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b text-slate-500 text-sm">
              <th className="py-2">Candidate Arm</th>
              <th className="py-2">Prior</th>
              <th className="py-2">Pulls</th>
              <th className="py-2">Expected Reward</th>
              <th className="py-2">UCB Bound</th>
              <th className="py-2">Cost/Pull</th>
              <th className="py-2">Knapsack Score</th>
            </tr>
          </thead>
          <tbody>
            {MOCK_BANDIT_STATE.arms.sort((a, b) => b.pulls - a.pulls).map((arm) => (
              <tr key={arm.id} className="border-b last:border-0 hover:bg-slate-50 transition-colors">
                <td className="py-3 px-2">
                  <div className="font-bold text-slate-700">{arm.component}</div>
                  <div className="text-xs text-slate-400 font-mono">{arm.id}</div>
                </td>
                <td className="py-3 px-2 text-sm text-slate-600">{arm.prior.toFixed(2)}</td>
                <td className="py-3 px-2">
                  <span className="font-bold text-indigo-600 bg-indigo-50 px-2 py-1 rounded">{arm.pulls}</span>
                </td>
                <td className="py-3 px-2">
                  <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden mt-1 max-w-[100px]">
                    <div className="bg-green-500 h-2" style={{ width: `${arm.expected_reward * 100}%` }}></div>
                  </div>
                  <div className="text-xs text-slate-500 mt-1">{arm.expected_reward.toFixed(2)}</div>
                </td>
                <td className="py-3 px-2 text-sm text-slate-600">
                  <span className="text-orange-500 font-medium">+{((arm.ucb - arm.expected_reward)).toFixed(2)}</span> ({arm.ucb.toFixed(2)})
                </td>
                <td className="py-3 px-2 text-sm font-mono text-slate-600">${arm.cost.toFixed(2)}</td>
                <td className="py-3 px-2 font-bold text-slate-700">{(arm.ucb / arm.cost).toFixed(1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
