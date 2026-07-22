"use client"
import React, { useState } from "react";

// ─── Types ────────────────────────────────────────────────────────────────────
type RecoveryStatus = "proposed" | "policy_checking" | "pending_approval" | "preparing" | "executing" | "verifying" | "committed" | "compensating" | "compensated" | "failed" | "cancelled";
type ExecutionMode = "dry_run" | "simulation" | "manual" | "approved";
type ActionType = "increase_top_k" | "retry_hybrid_retrieval" | "switch_stable_index" | "rerank" | "route_stable_model" | "disable_test_tool" | "quarantine_memory_ns" | "revert_prompt_version" | "rollback_component";

interface RecoveryProposal {
  proposalId: string;
  actionType: ActionType;
  executionMode: ExecutionMode;
  nodeId: string;
  params: Record<string, any>;
  policyDecision?: "allow" | "deny" | "needs_approval";
  status: RecoveryStatus;
  createdAt: string;
}

interface RollbackCapsule {
  capsuleId: string;
  previousState: Record<string, any>;
  targetState: Record<string, any>;
  status: "active" | "used" | "expired" | "voided";
  expiresAt: string;
}

interface CanaryMetrics {
  qualityPass: boolean;
  costPass: boolean;
  latencyPass: boolean;
  safetyPass: boolean;
  overallPass: boolean;
  deltas: {
    quality: number;
    cost: number;
    latency: number;
  };
}

interface StateEvent {
  from: string;
  to: string;
  reason: string;
  occurredAt: string;
}

interface RecoveryRecord {
  proposal: RecoveryProposal;
  capsule?: RollbackCapsule;
  metrics?: CanaryMetrics;
  eventLog: StateEvent[];
  escalationLog: string[];
}

// ─── Mock Data ────────────────────────────────────────────────────────────────
const MOCK_RECORD: RecoveryRecord = {
  proposal: {
    proposalId: "prop_7f9a2b",
    actionType: "rollback_component",
    executionMode: "simulation",
    nodeId: "pipeline_rag_v2",
    params: {
      component_id: "retriever_v2",
      target_version_id: "ver_A",
      expected_current_version_id: "ver_B",
    },
    policyDecision: "allow",
    status: "committed",
    createdAt: "2026-07-22T14:30:00Z",
  },
  capsule: {
    capsuleId: "cap_3d2c1a",
    previousState: { component_id: "retriever_v2", version_id: "ver_B" },
    targetState: { component_id: "retriever_v2", version_id: "ver_A" },
    status: "active",
    expiresAt: "2026-07-25T14:30:00Z",
  },
  metrics: {
    qualityPass: true,
    costPass: true,
    latencyPass: true,
    safetyPass: true,
    overallPass: true,
    deltas: {
      quality: +0.05,
      cost: -0.02,
      latency: -15.0,
    }
  },
  eventLog: [
    { from: "proposed", to: "policy_checking", reason: "Starting policy check", occurredAt: "2026-07-22T14:30:01Z" },
    { from: "policy_checking", to: "preparing", reason: "Policy allowed action", occurredAt: "2026-07-22T14:30:02Z" },
    { from: "preparing", to: "executing", reason: "Capsule cap_3d2c1a created", occurredAt: "2026-07-22T14:30:03Z" },
    { from: "executing", to: "verifying", reason: "Action executed successfully", occurredAt: "2026-07-22T14:30:05Z" },
    { from: "verifying", to: "committed", reason: "Canary verification passed", occurredAt: "2026-07-22T14:35:12Z" },
  ],
  escalationLog: []
};


// ─── Helpers ──────────────────────────────────────────────────────────────────
const STATUS_COLORS: Record<string, string> = {
  proposed: "bg-gray-100 text-gray-700",
  policy_checking: "bg-blue-100 text-blue-700",
  pending_approval: "bg-amber-100 text-amber-800",
  preparing: "bg-indigo-100 text-indigo-700",
  executing: "bg-purple-100 text-purple-700",
  verifying: "bg-cyan-100 text-cyan-800",
  committed: "bg-emerald-100 text-emerald-800 border-emerald-300 font-bold",
  compensating: "bg-orange-100 text-orange-800",
  compensated: "bg-emerald-100 text-emerald-800",
  failed: "bg-red-100 text-red-800 font-bold",
  cancelled: "bg-gray-200 text-gray-500",
};

// ─── Component ────────────────────────────────────────────────────────────────
export default function RecoveryConsole() {
  const record = MOCK_RECORD;
  const { proposal, capsule, metrics, eventLog, escalationLog } = record;

  return (
    <div className="min-h-screen bg-slate-50 font-sans pb-12">
      {/* Header */}
      <header className="bg-slate-900 text-white px-8 py-5 flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">Recovery Console</h1>
          <p className="text-slate-400 text-sm mt-1">
            DriftGuard-X v2 — Policy-Gated Recovery & Deterministic Rollback
          </p>
        </div>
        <div className="flex gap-3">
          <span className="px-3 py-1 bg-slate-800 border border-slate-700 rounded text-sm text-slate-300 font-mono">
            MODE: {proposal.executionMode.toUpperCase()}
          </span>
          <span className={`px-3 py-1 rounded border text-sm font-bold ${STATUS_COLORS[proposal.status]}`}>
            STATUS: {proposal.status.toUpperCase()}
          </span>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-8 py-8 grid grid-cols-3 gap-6">
        
        {/* Left Column (Proposal & Policy) */}
        <div className="col-span-1 space-y-6">
          {/* Proposal Card */}
          <div className="bg-white rounded-lg border shadow-sm p-5">
            <h2 className="text-sm font-bold text-slate-500 uppercase tracking-wide mb-4">Recovery Proposal</h2>
            <div className="space-y-3 text-sm">
              <div>
                <span className="text-slate-400 block text-xs">ID</span>
                <span className="font-mono">{proposal.proposalId}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-xs">Action Type</span>
                <span className="font-mono font-medium text-slate-900">{proposal.actionType}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-xs">Target Node</span>
                <span className="font-mono">{proposal.nodeId}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-xs">Parameters</span>
                <pre className="bg-slate-50 p-2 rounded border text-xs text-slate-700 mt-1 overflow-x-auto">
                  {JSON.stringify(proposal.params, null, 2)}
                </pre>
              </div>
            </div>
          </div>

          {/* Policy Decision Card */}
          <div className="bg-white rounded-lg border shadow-sm p-5">
            <h2 className="text-sm font-bold text-slate-500 uppercase tracking-wide mb-4">Policy Gate</h2>
            <div className="flex items-center gap-3">
              <span className={`px-3 py-1 rounded text-sm font-bold ${
                proposal.policyDecision === 'allow' ? 'bg-emerald-100 text-emerald-800' :
                proposal.policyDecision === 'deny' ? 'bg-red-100 text-red-800' : 'bg-amber-100 text-amber-800'
              }`}>
                {proposal.policyDecision?.toUpperCase() || "UNKNOWN"}
              </span>
              <span className="text-sm text-slate-600">Pre-execution check</span>
            </div>
          </div>
        </div>

        {/* Right Column (Execution, Verification, Capsule) */}
        <div className="col-span-2 space-y-6">
          
          {/* State Machine Log */}
          <div className="bg-white rounded-lg border shadow-sm p-5">
            <h2 className="text-sm font-bold text-slate-500 uppercase tracking-wide mb-4 flex justify-between">
              <span>Saga Execution Log</span>
            </h2>
            <div className="space-y-3">
              {eventLog.map((ev, i) => (
                <div key={i} className="flex gap-4 text-sm items-start">
                  <div className="text-slate-400 font-mono text-xs mt-0.5 whitespace-nowrap">
                    {ev.occurredAt.split('T')[1].replace('Z','')}
                  </div>
                  <div>
                    <span className="text-slate-500">{ev.from} &rarr; </span>
                    <span className={`px-1.5 py-0.5 rounded text-xs font-bold ${STATUS_COLORS[ev.to]}`}>{ev.to}</span>
                    <p className="text-slate-700 mt-1">{ev.reason}</p>
                  </div>
                </div>
              ))}
              {escalationLog.length > 0 && (
                <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded">
                  <h3 className="text-red-800 font-bold text-sm mb-2">ESCALATION LOG</h3>
                  <ul className="list-disc list-inside text-sm text-red-700 space-y-1">
                    {escalationLog.map((log, i) => <li key={i}>{log}</li>)}
                  </ul>
                </div>
              )}
            </div>
          </div>

          {/* Verification Metrics */}
          {metrics && (
            <div className="bg-white rounded-lg border shadow-sm p-5">
              <h2 className="text-sm font-bold text-slate-500 uppercase tracking-wide mb-4">Canary Verification</h2>
              <div className="grid grid-cols-4 gap-4">
                <MetricCard label="Quality" pass={metrics.qualityPass} delta={metrics.deltas.quality} suffix="" />
                <MetricCard label="Cost" pass={metrics.costPass} delta={metrics.deltas.cost} suffix="$" invertDeltaColor />
                <MetricCard label="Latency" pass={metrics.latencyPass} delta={metrics.deltas.latency} suffix="ms" invertDeltaColor />
                <MetricCard label="Safety" pass={metrics.safetyPass} delta={null} textOverride="No new violations" />
              </div>
              <div className="mt-4 pt-4 border-t flex items-center justify-between">
                <span className="text-sm font-medium text-slate-700">Overall Verification Result</span>
                <span className={`px-3 py-1 rounded font-bold text-sm ${metrics.overallPass ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'}`}>
                  {metrics.overallPass ? "PASSED" : "FAILED"}
                </span>
              </div>
            </div>
          )}

          {/* Rollback Capsule */}
          {capsule && (
            <div className="bg-white rounded-lg border shadow-sm p-5 border-l-4 border-l-indigo-500">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h2 className="text-sm font-bold text-slate-500 uppercase tracking-wide">Rollback Capsule</h2>
                  <p className="text-xs text-slate-400 font-mono mt-1">{capsule.capsuleId}</p>
                </div>
                <span className={`px-2 py-1 text-xs rounded border font-bold ${
                  capsule.status === 'active' ? 'bg-indigo-50 text-indigo-700 border-indigo-200' :
                  capsule.status === 'used' ? 'bg-slate-100 text-slate-600 border-slate-300' : 'bg-red-50 text-red-700 border-red-200'
                }`}>
                  {capsule.status.toUpperCase()}
                </span>
              </div>
              
              <div className="grid grid-cols-2 gap-6 text-sm">
                <div>
                  <h3 className="font-medium text-slate-700 mb-2">Previous State (Snapshot)</h3>
                  <pre className="bg-slate-50 p-2 rounded border text-xs text-slate-600 overflow-x-auto">
                    {JSON.stringify(capsule.previousState, null, 2)}
                  </pre>
                </div>
                <div>
                  <h3 className="font-medium text-slate-700 mb-2">Target State</h3>
                  <pre className="bg-slate-50 p-2 rounded border text-xs text-slate-600 overflow-x-auto">
                    {JSON.stringify(capsule.targetState, null, 2)}
                  </pre>
                </div>
              </div>

              <div className="mt-5 pt-4 border-t flex justify-end">
                <button 
                  disabled={capsule.status !== 'active'}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded shadow-sm transition-colors"
                >
                  Execute Manual Rollback
                </button>
              </div>
            </div>
          )}

        </div>
      </main>
    </div>
  );
}

function MetricCard({ label, pass, delta, suffix = "", invertDeltaColor = false, textOverride = "" }: any) {
  let deltaColor = "text-slate-500";
  if (delta !== null) {
    if (delta > 0) deltaColor = invertDeltaColor ? "text-red-600" : "text-emerald-600";
    if (delta < 0) deltaColor = invertDeltaColor ? "text-emerald-600" : "text-red-600";
  }

  return (
    <div className="border rounded-lg p-3 bg-slate-50 text-center">
      <div className="text-xs text-slate-500 uppercase mb-1">{label}</div>
      <div className="flex items-center justify-center gap-2">
        <span className={pass ? "text-emerald-500 font-bold" : "text-red-500 font-bold"}>
          {pass ? "✓" : "✗"}
        </span>
        {textOverride ? (
          <span className="text-sm font-medium text-slate-700">{textOverride}</span>
        ) : (
          <span className={`text-sm font-bold ${deltaColor}`}>
            {delta > 0 ? "+" : ""}{delta}{suffix}
          </span>
        )}
      </div>
    </div>
  );
}
