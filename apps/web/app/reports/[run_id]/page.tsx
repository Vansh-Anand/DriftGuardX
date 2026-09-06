"use client"
import React from 'react';

// ─── Types ────────────────────────────────────────────────────────────────────
type CertStatus = "CERTIFIED" | "UNCERTIFIED" | "REJECTED" | "INSUFFICIENT_EVIDENCE";
type EvidenceClassification = "PRODUCTION" | "REAL_CONTROLLED_EXPERIMENT" | "SYNTHETIC_SIMULATION" | "TEST_FIXTURE" | "UNVERIFIED";

interface MockReport {
  run_id: string;
  abstention_triggered: boolean;
  limitations: string[];
  recommended_next_step: string;
  // Certification fields (Prompt 10)
  certificate_status: CertStatus;
  evidence_class: EvidenceClassification;
  bound_method: string;
  epsilon: number;
  delta: number;
  nominal_confidence: number;
  observed_coverage: number;
  calibration_version: string;
  calibration_age_days: number;
  assumptions_met: string[];
  assumptions_violated: string[];
  human_review_required: boolean;
  block_automated_action: boolean;
  highest_posterior?: number;
  next_action?: string;
  ranked_candidates: Array<{
    id: string;
    component_type: string;
    intervention_type: string;
    aggregate_score: number;
    reliability_improvement_mean: number;
    reliability_improvement_variance: number;
    cost_delta_usd: number;
    latency_delta_ms: number;
    invalid_rate: number;
    trials_n: number;
    is_negative_control: boolean;
  }>;
}

const MOCK_REPORT: MockReport = {
  run_id: "r_987654321",
  abstention_triggered: false,
  limitations: [
    "Learned attribution only. Does not imply causal proof beyond exhaustive replay bounds.",
    "Cost constraints limited repeated trials to N=35.",
  ],
  recommended_next_step: "Approve Rollback of Retriever to v1.",
  // Certification fields
  certificate_status: "INSUFFICIENT_EVIDENCE",
  highest_posterior: 0.51,
  next_action: "collect another replay",
  evidence_class: "SYNTHETIC_SIMULATION",
  bound_method: "hoeffding",
  epsilon: 0.087,
  delta: 0.10,
  nominal_confidence: 0.90,
  observed_coverage: 0.883,
  calibration_version: "v1.0",
  calibration_age_days: 4.2,
  assumptions_met: [
    "All 35 rewards in [0, 1].",
    "n=35 ≥ 30 (low-n threshold).",
    "i.i.d. assumption accepted under fault-injection lab conditions.",
    "Empirical coverage 88.3% within 5pp of 90% nominal.",
  ],
  assumptions_violated: [],
  human_review_required: false,
  block_automated_action: false,
  ranked_candidates: [
    {
      id: "rc_1", component_type: "retriever", intervention_type: "ROLLBACK",
      aggregate_score: 8.5, reliability_improvement_mean: 0.10,
      reliability_improvement_variance: 0.0001, cost_delta_usd: 0.01,
      latency_delta_ms: 10.0, invalid_rate: 0.0, trials_n: 35, is_negative_control: false,
    },
    {
      id: "rc_2", component_type: "generator", intervention_type: "NO_OP",
      aggregate_score: 0.0, reliability_improvement_mean: 0.001,
      reliability_improvement_variance: 0.0005, cost_delta_usd: 0.0,
      latency_delta_ms: 0.0, invalid_rate: 0.0, trials_n: 35, is_negative_control: true,
    },
    {
      id: "rc_3", component_type: "policy_check", intervention_type: "DISABLE",
      aggregate_score: 0.0, reliability_improvement_mean: -0.05,
      reliability_improvement_variance: 0.001, cost_delta_usd: 0.0,
      latency_delta_ms: -50.0, invalid_rate: 0.33, trials_n: 35, is_negative_control: false,
    },
  ],
};

// ─── CertificationBadge ───────────────────────────────────────────────────────
// CRITICAL GATE: This component will NEVER render a "CERTIFIED" badge unless
// certificate_status === "CERTIFIED". UNCERTIFIED and REJECTED always show
// a warning and block the Execute Action button.
function CertificationBadge({ report }: { report: MockReport }) {
  const { certificate_status, bound_method, epsilon, delta, nominal_confidence,
    observed_coverage, calibration_version, calibration_age_days,
    assumptions_met, assumptions_violated, highest_posterior, next_action } = report;

  const badgeConfig = {
    CERTIFIED: {
      bg: "bg-emerald-50", border: "border-emerald-500", text: "text-emerald-800",
      dot: "bg-emerald-500", label: "✓ Statistically Bounded",
      subtext: "statistically bounded under listed assumptions",
    },
    UNCERTIFIED: {
      bg: "bg-amber-50", border: "border-amber-500", text: "text-amber-800",
      dot: "bg-amber-500", label: "⚠ Uncertified — Human Review Required",
      subtext: "one or more certification gates failed",
    },
    REJECTED: {
      bg: "bg-red-50", border: "border-red-600", text: "text-red-800",
      dot: "bg-red-600", label: "✗ Rejected — Automated Actions Blocked",
      subtext: "critical assumption violations; manual review mandatory",
    },
    INSUFFICIENT_EVIDENCE: {
      bg: "bg-slate-100", border: "border-slate-400", text: "text-slate-700",
      dot: "bg-slate-400", label: "⚠ INSUFFICIENT EVIDENCE",
      subtext: `posterior (${highest_posterior}) did not meet the required threshold. Next action: ${next_action}`,
    },
  }[certificate_status];

  return (
    <section className={`mb-6 ${badgeConfig.bg} border-l-4 ${badgeConfig.border} p-5 rounded-lg`}>
      <div className="flex items-center gap-3 mb-3">
        <span className={`inline-block w-3 h-3 rounded-full ${badgeConfig.dot}`}></span>
        <h3 className={`font-bold text-base ${badgeConfig.text}`}>{badgeConfig.label}</h3>
        <span className={`text-xs px-2 py-0.5 rounded border ${badgeConfig.border} ${badgeConfig.text}`}>
          {certificate_status}
        </span>
      </div>
      <p className={`text-xs italic mb-4 ${badgeConfig.text}`}>
        This diagnosis is {badgeConfig.subtext}. It does NOT constitute a system safety guarantee.
      </p>
      <div className="mb-4 rounded border border-amber-500 bg-amber-50 p-3 text-xs font-semibold text-amber-900">
        Evidence provenance: {report.evidence_class.replaceAll("_", " ")}.
        {report.evidence_class === "SYNTHETIC_SIMULATION" &&
          " Synthetic evidence cannot authorize production execution."}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
        <div className="bg-white/60 rounded p-2">
          <div className="font-semibold text-gray-600 mb-0.5">Bound Method</div>
          <div className="font-mono font-bold">{bound_method ?? "—"}</div>
        </div>
        <div className="bg-white/60 rounded p-2">
          <div className="font-semibold text-gray-600 mb-0.5">ε (margin)</div>
          <div className="font-mono font-bold">{epsilon != null ? `±${epsilon.toFixed(3)}` : "—"}</div>
        </div>
        <div className="bg-white/60 rounded p-2">
          <div className="font-semibold text-gray-600 mb-0.5">Nominal / Observed Coverage</div>
          <div className="font-mono font-bold">
            {nominal_confidence != null ? `${(nominal_confidence * 100).toFixed(0)}%` : "—"}
            {" / "}
            {observed_coverage != null
              ? <span className={observed_coverage >= (nominal_confidence - 0.05) ? "text-emerald-600" : "text-red-600"}>
                  {(observed_coverage * 100).toFixed(1)}%
                </span>
              : "—"}
          </div>
        </div>
        <div className="bg-white/60 rounded p-2">
          <div className="font-semibold text-gray-600 mb-0.5">Calibration</div>
          <div className="font-mono font-bold">{calibration_version} · {calibration_age_days?.toFixed(1)}d old</div>
        </div>
      </div>

      {assumptions_met.length > 0 && (
        <details className="mt-3">
          <summary className="text-xs font-semibold text-gray-500 cursor-pointer">
            Assumptions ({assumptions_met.length} met{assumptions_violated.length > 0 ? `, ${assumptions_violated.length} violated` : ""})
          </summary>
          <ul className="mt-2 text-xs text-gray-600 space-y-0.5 ml-3">
            {assumptions_met.map((a, i) => <li key={i} className="text-emerald-700">✓ {a}</li>)}
            {assumptions_violated.map((a, i) => <li key={i} className="text-red-600">✗ {a}</li>)}
          </ul>
        </details>
      )}
    </section>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function RootCauseReportPage({ params }: { params: { run_id: string } }) {
  const canExecute =
    MOCK_REPORT.certificate_status === "CERTIFIED" &&
    MOCK_REPORT.evidence_class !== "SYNTHETIC_SIMULATION" &&
    !MOCK_REPORT.block_automated_action;

  return (
    <div className="p-8 max-w-6xl mx-auto font-sans bg-gray-50 min-h-screen">
      <header className="mb-8 border-b pb-4">
        <h1 className="text-3xl font-bold mb-2 text-indigo-900">Root Cause Diagnosis Report</h1>
        <p className="text-gray-600 font-mono text-sm">Run: {params.run_id}</p>
      </header>

      {/* Gated Certification Badge */}
      <CertificationBadge report={MOCK_REPORT} />

      {/* Causal Language Disclaimer */}
      <section className="mb-6 bg-blue-50 border-l-4 border-blue-500 p-4 rounded text-sm text-blue-900">
        <h3 className="font-bold mb-1">Causal Evidence Limitations</h3>
        <ul className="list-disc ml-5 space-y-1">
          {MOCK_REPORT.limitations.map((limit, i) => <li key={i}>{limit}</li>)}
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

      {/* Diagnostic Conclusion — GATED by certificate_status */}
      <section className={`bg-white rounded-lg shadow-sm border p-6 border-t-4 ${
        canExecute ? "border-t-emerald-500" :
        MOCK_REPORT.certificate_status === "REJECTED" ? "border-t-red-600" : "border-t-amber-500"
      }`}>
        <h2 className="text-lg font-bold mb-2">Diagnostic Conclusion</h2>

        {MOCK_REPORT.abstention_triggered ? (
          <p className="text-gray-700">
            <strong className="text-red-600">Abstention Triggered:</strong> Insufficient evidence.
          </p>
        ) : (
          <div>
            <p className="text-gray-700 mb-4">A likely recoverable root cause has been identified.</p>
            <div className={`border p-4 rounded flex items-center justify-between ${
              canExecute ? "bg-emerald-50 border-emerald-200 text-emerald-900" : "bg-amber-50 border-amber-200 text-amber-900"
            }`}>
              <div>
                <span className="block text-sm font-bold mb-1">Recommended Action</span>
                <span>{MOCK_REPORT.recommended_next_step}</span>
                {!canExecute && (
                  <p className="text-xs mt-2 font-semibold">
                    ⚠ Automated execution is blocked. Human review required before proceeding.
                  </p>
                )}
              </div>
              {/* CRITICAL: Execute button is DISABLED unless CERTIFIED */}
              <button
                disabled={!canExecute}
                id="execute-action-button"
                className={`px-6 py-2 rounded font-medium transition-colors ${
                  canExecute
                    ? "bg-emerald-600 text-white hover:bg-emerald-700"
                    : "bg-gray-300 text-gray-500 cursor-not-allowed"
                }`}
              >
                {canExecute ? "Execute Action" : "Blocked — Uncertified"}
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
