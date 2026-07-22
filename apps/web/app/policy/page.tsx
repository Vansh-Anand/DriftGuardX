"use client"
import React, { useState } from "react";

// ─── Types ────────────────────────────────────────────────────────────────────
type Verdict = "allow" | "deny" | "needs_approval";
type RiskTier = "low" | "medium" | "high" | "critical";
type ApprovalStatus = "pending" | "approved" | "denied" | "expired" | "break_glass";

interface HierarchyNode {
  nodeId: string;
  level: "organization" | "business_unit" | "pipeline" | "agent";
  label: string;
  children?: HierarchyNode[];
}

interface ActionMatrixRow {
  action: string;
  tier: RiskTier;
  orgVerdict: Verdict;
  pipelineVerdict: Verdict;
  effectiveVerdict: Verdict;
  winningLevel: string;
  requiresApproval: boolean;
  twoPersonControl: boolean;
}

interface ApprovalItem {
  requestId: string;
  action: string;
  requester: string;
  nodeId: string;
  tier: RiskTier;
  status: ApprovalStatus;
  createdAt: string;
  expiresAt: string;
}

// ─── Mock Data ────────────────────────────────────────────────────────────────
const MOCK_HIERARCHY: HierarchyNode = {
  nodeId: "org_acme",
  level: "organization",
  label: "ACME Corp",
  children: [
    {
      nodeId: "bu_platform",
      level: "business_unit",
      label: "Platform Team",
      children: [
        {
          nodeId: "pipeline_rag_v2",
          level: "pipeline",
          label: "RAG v2 Pipeline",
          children: [
            { nodeId: "agent_retriever", level: "agent", label: "Retriever Agent" },
            { nodeId: "agent_reranker", level: "agent", label: "Reranker Agent" },
          ],
        },
        {
          nodeId: "pipeline_chat",
          level: "pipeline",
          label: "Chat Pipeline",
          children: [
            { nodeId: "agent_chat_gen", level: "agent", label: "Chat Generator" },
          ],
        },
      ],
    },
    {
      nodeId: "bu_research",
      level: "business_unit",
      label: "Research Team",
      children: [
        {
          nodeId: "pipeline_exp",
          level: "pipeline",
          label: "Experimental Pipeline (Restricted)",
          children: [],
        },
      ],
    },
  ],
};

const MOCK_ACTION_MATRIX: ActionMatrixRow[] = [
  { action: "read_trace", tier: "low", orgVerdict: "allow", pipelineVerdict: "allow", effectiveVerdict: "allow", winningLevel: "organization", requiresApproval: false, twoPersonControl: false },
  { action: "schedule_replay", tier: "medium", orgVerdict: "allow", pipelineVerdict: "allow", effectiveVerdict: "needs_approval", winningLevel: "organization", requiresApproval: true, twoPersonControl: false },
  { action: "apply_rollback", tier: "high", orgVerdict: "needs_approval", pipelineVerdict: "deny", effectiveVerdict: "deny", winningLevel: "pipeline", requiresApproval: false, twoPersonControl: true },
  { action: "delete_memory", tier: "critical", orgVerdict: "deny", pipelineVerdict: "deny", effectiveVerdict: "deny", winningLevel: "organization", requiresApproval: false, twoPersonControl: true },
  { action: "apply_intervention", tier: "high", orgVerdict: "needs_approval", pipelineVerdict: "needs_approval", effectiveVerdict: "needs_approval", winningLevel: "organization", requiresApproval: true, twoPersonControl: true },
];

const MOCK_APPROVALS: ApprovalItem[] = [
  { requestId: "req_001", action: "apply_rollback", requester: "alice", nodeId: "pipeline_rag_v2", tier: "high", status: "pending", createdAt: "2026-07-22T12:00Z", expiresAt: "2026-07-23T12:00Z" },
  { requestId: "req_002", action: "schedule_replay", requester: "bob", nodeId: "pipeline_chat", tier: "medium", status: "approved", createdAt: "2026-07-22T09:00Z", expiresAt: "2026-07-23T09:00Z" },
  { requestId: "req_003", action: "apply_intervention", requester: "charlie", nodeId: "pipeline_exp", tier: "high", status: "denied", createdAt: "2026-07-21T18:00Z", expiresAt: "2026-07-22T18:00Z" },
  { requestId: "req_004", action: "apply_rollback", requester: "diana", nodeId: "pipeline_rag_v2", tier: "high", status: "break_glass", createdAt: "2026-07-22T10:30Z", expiresAt: "2026-07-23T10:30Z" },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────
const VERDICT_STYLE: Record<Verdict, string> = {
  allow: "bg-emerald-100 text-emerald-800 border-emerald-300",
  deny: "bg-red-100 text-red-800 border-red-300",
  needs_approval: "bg-amber-100 text-amber-800 border-amber-300",
};
const VERDICT_LABEL: Record<Verdict, string> = {
  allow: "✓ Allow",
  deny: "✗ Deny",
  needs_approval: "⧗ Approval",
};
const TIER_STYLE: Record<RiskTier, string> = {
  low: "bg-slate-100 text-slate-700",
  medium: "bg-blue-100 text-blue-700",
  high: "bg-orange-100 text-orange-700",
  critical: "bg-red-100 text-red-800 font-bold",
};
const STATUS_STYLE: Record<ApprovalStatus, string> = {
  pending: "bg-amber-100 text-amber-800",
  approved: "bg-emerald-100 text-emerald-800",
  denied: "bg-red-100 text-red-800",
  expired: "bg-gray-100 text-gray-500",
  break_glass: "bg-purple-100 text-purple-800",
};
const LEVEL_INDENT: Record<string, string> = {
  organization: "ml-0",
  business_unit: "ml-4",
  pipeline: "ml-8",
  agent: "ml-12",
};
const LEVEL_COLOR: Record<string, string> = {
  organization: "border-indigo-400 bg-indigo-50",
  business_unit: "border-blue-400 bg-blue-50",
  pipeline: "border-teal-400 bg-teal-50",
  agent: "border-slate-400 bg-slate-50",
};

// ─── HierarchyTree ────────────────────────────────────────────────────────────
function HierarchyTree({ node, selected, onSelect }: {
  node: HierarchyNode;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div className={LEVEL_INDENT[node.level]}>
      <button
        id={`node-${node.nodeId}`}
        onClick={() => onSelect(node.nodeId)}
        className={`w-full text-left my-1 px-3 py-2 rounded border text-sm font-medium
          ${LEVEL_COLOR[node.level]}
          ${selected === node.nodeId ? "ring-2 ring-indigo-500" : ""}
          hover:opacity-80 transition-opacity`}
      >
        <span className="text-xs text-gray-400 mr-2">[{node.level}]</span>
        {node.label}
      </button>
      {node.children?.map((child) => (
        <HierarchyTree key={child.nodeId} node={child} selected={selected} onSelect={onSelect} />
      ))}
    </div>
  );
}

// ─── VerdictBadge ─────────────────────────────────────────────────────────────
function VerdictBadge({ verdict }: { verdict: Verdict }) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded border font-mono ${VERDICT_STYLE[verdict]}`}>
      {VERDICT_LABEL[verdict]}
    </span>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function PolicyPage() {
  const [selectedNode, setSelectedNode] = useState<string | null>("pipeline_rag_v2");
  const [activeTab, setActiveTab] = useState<"hierarchy" | "matrix" | "queue">("hierarchy");

  const pendingApprovals = MOCK_APPROVALS.filter(a => a.status === "pending");

  return (
    <div className="min-h-screen bg-gray-50 font-sans">
      {/* Header */}
      <header className="bg-indigo-900 text-white px-8 py-5">
        <h1 className="text-2xl font-bold">Policy Administration Console</h1>
        <p className="text-indigo-300 text-sm mt-1">
          DriftGuard-X v2 — Multi-Tenant Policy Hierarchy & Approval Workflows
        </p>
      </header>

      {/* Tabs */}
      <nav className="bg-white border-b px-8 flex gap-0">
        {(["hierarchy", "matrix", "queue"] as const).map(tab => (
          <button
            key={tab}
            id={`tab-${tab}`}
            onClick={() => setActiveTab(tab)}
            className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors capitalize ${
              activeTab === tab
                ? "border-indigo-600 text-indigo-700"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab === "queue"
              ? `Approval Queue ${pendingApprovals.length > 0 ? `(${pendingApprovals.length})` : ""}`
              : tab === "hierarchy" ? "Policy Hierarchy" : "Action Matrix"}
          </button>
        ))}
      </nav>

      <main className="px-8 py-6 max-w-7xl mx-auto">

        {/* ── Hierarchy Tab ──────────────────────────────────────────────────── */}
        {activeTab === "hierarchy" && (
          <div className="grid grid-cols-3 gap-6">
            {/* Tree */}
            <div className="col-span-1 bg-white rounded-lg border shadow-sm p-4">
              <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wide mb-3">
                Org / BU / Pipeline / Agent
              </h2>
              <HierarchyTree node={MOCK_HIERARCHY} selected={selectedNode} onSelect={setSelectedNode} />
            </div>

            {/* Effective Policy Panel */}
            <div className="col-span-2 bg-white rounded-lg border shadow-sm p-6">
              <h2 className="text-lg font-semibold mb-4 text-indigo-900">
                Effective Policy: <span className="font-mono text-sm">{selectedNode ?? "—"}</span>
              </h2>
              {selectedNode ? (
                <div>
                  <p className="text-xs text-gray-500 mb-4">
                    Shows the computed effective policy for this node — rules from all ancestor
                    levels merged with tightening-only precedence. DENY always wins.
                  </p>
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr className="border-b text-gray-500 text-xs">
                        <th className="py-2 text-left">Action</th>
                        <th className="py-2 text-left">Tier</th>
                        <th className="py-2 text-left">Org</th>
                        <th className="py-2 text-left">Pipeline</th>
                        <th className="py-2 text-left font-bold text-indigo-700">Effective</th>
                        <th className="py-2 text-left">Won At</th>
                        <th className="py-2 text-left">2PC</th>
                      </tr>
                    </thead>
                    <tbody>
                      {MOCK_ACTION_MATRIX.map(row => (
                        <tr key={row.action} className="border-b last:border-0 hover:bg-gray-50">
                          <td className="py-2 font-mono text-xs">{row.action}</td>
                          <td className="py-2">
                            <span className={`text-xs px-1.5 py-0.5 rounded ${TIER_STYLE[row.tier]}`}>
                              {row.tier.toUpperCase()}
                            </span>
                          </td>
                          <td className="py-2"><VerdictBadge verdict={row.orgVerdict} /></td>
                          <td className="py-2"><VerdictBadge verdict={row.pipelineVerdict} /></td>
                          <td className="py-2 font-bold"><VerdictBadge verdict={row.effectiveVerdict} /></td>
                          <td className="py-2 text-xs text-gray-500">{row.winningLevel}</td>
                          <td className="py-2 text-xs">{row.twoPersonControl ? "✓" : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded text-xs text-blue-800">
                    <strong>Inheritance proof:</strong> Every effective rule can be traced to its source
                    level (Won At column). DENY from pipeline_rag_v2 overrides org NEEDS_APPROVAL for
                    apply_rollback per tightening-only rules.
                  </div>
                </div>
              ) : (
                <p className="text-gray-400 text-sm">Select a node in the hierarchy to view its effective policy.</p>
              )}
            </div>
          </div>
        )}

        {/* ── Action Matrix Tab ──────────────────────────────────────────────── */}
        {activeTab === "matrix" && (
          <div className="bg-white rounded-lg border shadow-sm p-6">
            <h2 className="text-lg font-semibold mb-2 text-indigo-900">Action Risk Matrix</h2>
            <p className="text-xs text-gray-500 mb-4">
              All DriftGuard-X actions with their risk tier and approval requirements.
              HIGH/CRITICAL actions require human approval; CRITICAL requires two-person control.
            </p>
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b text-gray-500 text-xs">
                  <th className="py-2 text-left">Action</th>
                  <th className="py-2 text-left">Risk Tier</th>
                  <th className="py-2 text-left">Effective Verdict</th>
                  <th className="py-2 text-left">Approval Required</th>
                  <th className="py-2 text-left">Two-Person Control</th>
                </tr>
              </thead>
              <tbody>
                {MOCK_ACTION_MATRIX.map(row => (
                  <tr key={row.action} className="border-b last:border-0 hover:bg-gray-50">
                    <td className="py-2 font-mono text-xs">{row.action}</td>
                    <td className="py-2">
                      <span className={`text-xs px-2 py-0.5 rounded ${TIER_STYLE[row.tier]}`}>
                        {row.tier.toUpperCase()}
                      </span>
                    </td>
                    <td className="py-2"><VerdictBadge verdict={row.effectiveVerdict} /></td>
                    <td className="py-2 text-center text-sm">{row.requiresApproval ? "✓" : "—"}</td>
                    <td className="py-2 text-center text-sm">{row.twoPersonControl ? "✓" : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* ── Approval Queue Tab ─────────────────────────────────────────────── */}
        {activeTab === "queue" && (
          <div className="bg-white rounded-lg border shadow-sm p-6">
            <h2 className="text-lg font-semibold mb-2 text-indigo-900">Approval Queue</h2>
            <p className="text-xs text-gray-500 mb-4">
              Pending and historical approval decisions. Self-approval is blocked. Break-glass
              decisions are flagged for post-hoc security review.
            </p>
            <div className="space-y-3">
              {MOCK_APPROVALS.map(item => (
                <div
                  key={item.requestId}
                  id={`approval-${item.requestId}`}
                  className={`border rounded-lg p-4 ${item.status === "pending" ? "border-amber-300 bg-amber-50" : "border-gray-200"}`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm font-bold">{item.action}</span>
                      <span className={`text-xs px-1.5 py-0.5 rounded ${TIER_STYLE[item.tier]}`}>
                        {item.tier.toUpperCase()}
                      </span>
                      {item.status === "break_glass" && (
                        <span className="text-xs px-2 py-0.5 rounded bg-purple-100 text-purple-800 font-bold">
                          ⚡ BREAK GLASS — POST-HOC REVIEW REQUIRED
                        </span>
                      )}
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded ${STATUS_STYLE[item.status]}`}>
                      {item.status.replace("_", " ").toUpperCase()}
                    </span>
                  </div>
                  <div className="text-xs text-gray-500 flex gap-4">
                    <span>Requester: <strong>{item.requester}</strong></span>
                    <span>Node: <strong>{item.nodeId}</strong></span>
                    <span>Created: {item.createdAt}</span>
                    <span>Expires: {item.expiresAt}</span>
                  </div>
                  {item.status === "pending" && (
                    <div className="mt-3 flex gap-2">
                      <button
                        id={`approve-${item.requestId}`}
                        className="px-3 py-1.5 text-xs bg-emerald-600 text-white rounded hover:bg-emerald-700 font-medium"
                      >
                        Approve
                      </button>
                      <button
                        id={`deny-${item.requestId}`}
                        className="px-3 py-1.5 text-xs bg-red-600 text-white rounded hover:bg-red-700 font-medium"
                      >
                        Deny
                      </button>
                      <button
                        id={`comment-${item.requestId}`}
                        className="px-3 py-1.5 text-xs border border-gray-300 rounded hover:bg-gray-50"
                      >
                        Add Comment
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
