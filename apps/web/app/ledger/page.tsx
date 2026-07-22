"use client"
import React, { useState } from "react";

// ─── Mock Data ────────────────────────────────────────────────────────────────
const MOCK_CHAIN = {
  headHash: "e4d909c290d0fb1ca068ffaddf22cbd0a4b6557ec651b7be9e527f311df93bc5",
  size: 3,
  status: "VERIFIED",
  lastVerifiedAt: "2026-07-22T14:35:12Z"
};

const MOCK_CERTS = [
  {
    cert_id: "cert_9a2b7f",
    tenant_id: "tenant_acme",
    pipeline_id: "pipeline_rag_v2",
    run_id: "run_001",
    timestamp: "2026-07-22T14:35:10Z",
    action_result: "COMMITTED",
    verification_result: "PASSED",
    certification_method: "Ed25519",
    signer_key_id: "KMS-production-01",
    previous_cert_hash: "8f4a13d...",
    cert_hash: "e4d909c290d0fb1ca068ffaddf22cbd0a4b6557ec651b7be9e527f311df93bc5",
    intervention_vector: {
      component_id: "retriever_v2",
      new_top_k: 20
    }
  },
  {
    cert_id: "cert_3d1a8c",
    tenant_id: "tenant_acme",
    pipeline_id: "pipeline_rag_v2",
    run_id: "run_002",
    timestamp: "2026-07-21T09:12:00Z",
    action_result: "COMPENSATED",
    verification_result: "FAILED (Quality Drop)",
    certification_method: "Ed25519",
    signer_key_id: "KMS-production-01",
    previous_cert_hash: "GENESIS",
    cert_hash: "8f4a13d8a9b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8",
    intervention_vector: {
      component_id: "llm_router",
      stable_model_alias: "gpt-3.5"
    }
  }
];


// ─── Component ────────────────────────────────────────────────────────────────
export default function LedgerConsole() {
  return (
    <div className="min-h-screen bg-slate-50 font-sans pb-12">
      {/* Header */}
      <header className="bg-slate-900 text-white px-8 py-5 flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">Cryptographic Ledger</h1>
          <p className="text-slate-400 text-sm mt-1">
            DriftGuard-X v2 — Append-only Hash-Chained Recovery Certificates
          </p>
        </div>
        <div className="flex gap-3">
          <span className="px-3 py-1 bg-slate-800 border border-slate-700 rounded text-sm text-slate-300 font-mono">
            HEAD: {MOCK_CHAIN.headHash.substring(0, 16)}...
          </span>
          <span className="px-3 py-1 rounded border text-sm font-bold bg-emerald-100 text-emerald-800 border-emerald-300">
            CHAIN STATUS: {MOCK_CHAIN.status}
          </span>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-8 py-8 space-y-6">
        
        {/* Verification Overview Card */}
        <div className="bg-white rounded-lg border shadow-sm p-6 flex justify-between items-center">
          <div>
            <h2 className="text-lg font-bold text-slate-800">Ledger Integrity</h2>
            <p className="text-sm text-slate-500 mt-1">
              Last verified: {new Date(MOCK_CHAIN.lastVerifiedAt).toLocaleString()}
            </p>
          </div>
          <div className="flex gap-8">
            <div className="text-center">
              <div className="text-2xl font-bold text-slate-800">{MOCK_CHAIN.size}</div>
              <div className="text-xs text-slate-500 uppercase tracking-wide">Certificates</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-emerald-600">Valid</div>
              <div className="text-xs text-slate-500 uppercase tracking-wide">Hash Chain</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-emerald-600">Valid</div>
              <div className="text-xs text-slate-500 uppercase tracking-wide">Signatures</div>
            </div>
          </div>
          <div className="flex gap-3">
            <button className="px-4 py-2 border rounded shadow-sm text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors">
              Verify Chain
            </button>
            <button className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded shadow-sm text-sm font-medium transition-colors">
              Export Bundle
            </button>
          </div>
        </div>

        {/* Certificate Feed */}
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-500 uppercase tracking-wide">Certificate Chain (Latest First)</h2>
          
          {MOCK_CERTS.map((cert, idx) => (
            <div key={cert.cert_id} className="bg-white rounded-lg border shadow-sm overflow-hidden flex flex-col">
              {/* Card Header (Linkage) */}
              <div className="bg-slate-100 px-5 py-2 border-b flex justify-between items-center text-xs font-mono text-slate-500">
                <div className="flex items-center gap-2">
                  <span className="bg-slate-200 px-2 py-0.5 rounded text-slate-600">CERT HASH</span>
                  <span className="text-slate-700">{cert.cert_hash}</span>
                </div>
                <div className="flex items-center gap-2 opacity-70">
                  <span className="bg-slate-200 px-2 py-0.5 rounded">PREV HASH</span>
                  <span>{cert.previous_cert_hash}</span>
                </div>
              </div>

              {/* Card Body */}
              <div className="p-5 grid grid-cols-4 gap-6">
                
                {/* Meta */}
                <div className="col-span-1 space-y-4 text-sm">
                  <div>
                    <div className="text-xs text-slate-400 uppercase">Certificate ID</div>
                    <div className="font-medium text-slate-800">{cert.cert_id}</div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-400 uppercase">Timestamp</div>
                    <div className="text-slate-600">{new Date(cert.timestamp).toLocaleString()}</div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-400 uppercase">Target</div>
                    <div className="text-slate-600">{cert.tenant_id} / {cert.pipeline_id}</div>
                  </div>
                </div>

                {/* Intervention & Outcome */}
                <div className="col-span-2 space-y-4">
                  <div>
                    <div className="text-xs text-slate-400 uppercase mb-1">Intervention Vector</div>
                    <pre className="bg-slate-50 p-2 rounded border text-xs text-slate-700 font-mono overflow-x-auto">
                      {JSON.stringify(cert.intervention_vector, null, 2)}
                    </pre>
                  </div>
                  <div className="flex gap-4">
                    <div>
                      <div className="text-xs text-slate-400 uppercase">Action Result</div>
                      <div className={`text-sm font-bold ${cert.action_result === 'COMMITTED' ? 'text-emerald-600' : 'text-orange-600'}`}>
                        {cert.action_result}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-400 uppercase">Canary Verification</div>
                      <div className={`text-sm font-bold ${cert.verification_result.startsWith('PASSED') ? 'text-emerald-600' : 'text-red-600'}`}>
                        {cert.verification_result}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Crypto Proof */}
                <div className="col-span-1 space-y-4 text-sm">
                  <div>
                    <div className="text-xs text-slate-400 uppercase">Signer Identity</div>
                    <div className="font-mono text-indigo-600 bg-indigo-50 px-2 py-1 rounded border border-indigo-100 inline-block mt-1">
                      {cert.signer_key_id}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-400 uppercase">Method</div>
                    <div className="text-slate-600">{cert.certification_method}</div>
                  </div>
                  <div className="pt-2 border-t mt-4 flex items-center gap-2">
                    <span className="text-emerald-500 font-bold">✓</span>
                    <span className="text-xs font-bold text-slate-700 uppercase tracking-wide">Signature Valid</span>
                  </div>
                </div>

              </div>
            </div>
          ))}
        </div>

      </main>
    </div>
  );
}
