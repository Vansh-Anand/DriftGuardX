'use client';
import { PageLayout } from '@/components/PageLayout';
import Link from 'next/link';

export default function RationalePage() {
  const badge = (
    <span className="font-mono text-[10px] border border-[#0a0a0a] px-3 py-1.5 uppercase tracking-widest bg-[#0a0a0a] text-[#ECEAE2]">
      Rationale Certified
    </span>
  );

  return (
    <PageLayout title="Diagnosis Rationale" subtitle="Natural language reasoning for recovery decisions" badge={badge}>
      <div className="p-8">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Executive Summary */}
          <div className="border border-[#0a0a0a] p-6">
            <div className="font-mono text-[10px] tracking-[0.15em] uppercase text-[#888] mb-4">Executive Summary</div>
            <div className="space-y-4 font-mono text-xs text-[#0a0a0a] leading-relaxed">
              <div className="border-l-4 border-[#0a0a0a] pl-4 py-1">
                <span className="font-bold">[SYSTEM STABILITY ALERT]</span>
              </div>
              <p>DriftGuard-X detected a reliability drop in the <strong>RAG Pipeline</strong>.</p>
              <div className="border border-[#0a0a0a]/20 p-4 space-y-2">
                <div className="flex justify-between">
                  <span className="text-[#888]">Affected Component</span>
                  <span className="font-bold">Embeddings Model</span>
                </div>
                <div className="flex justify-between border-t border-[#0a0a0a]/10 pt-2">
                  <span className="text-[#888]">Reliability Drop</span>
                  <span className="font-bold text-red-600">0.41 (Critical)</span>
                </div>
                <div className="flex justify-between border-t border-[#0a0a0a]/10 pt-2">
                  <span className="text-[#888]">Baseline</span>
                  <span>0.99</span>
                </div>
                <div className="flex justify-between border-t border-[#0a0a0a]/10 pt-2">
                  <span className="text-[#888]">Cause</span>
                  <span>Version drift (v3.0 → v3.1)</span>
                </div>
              </div>
              <div className="bg-[#0a0a0a] text-[#ECEAE2] p-4">
                <span className="text-[10px] uppercase tracking-widest text-[#888] block mb-1">Recommended Action</span>
                <span className="font-bold">Rollback Embeddings Model to v2.0</span>
              </div>
            </div>
          </div>

          {/* Reasoning Chain */}
          <div className="border border-[#0a0a0a] p-6">
            <div className="font-mono text-[10px] tracking-[0.15em] uppercase text-[#888] mb-4">Reasoning Chain</div>
            <div className="space-y-0">
              {[
                { step: '01', label: 'Symptom Detection', desc: 'Retrieval overlap dropped below 0.5 threshold. Unsupported claim rate exceeded 0.10.' },
                { step: '02', label: 'Graph Attribution', desc: 'Causal graph traced symptom propagation from Vector Retriever ← Embeddings Model.' },
                { step: '03', label: 'Counterfactual Replay', desc: '35 replay trials with SWAP_RETRIEVER intervention. Reliability improvement: +10% (mean).' },
                { step: '04', label: 'Statistical Certification', desc: 'Hoeffding bound: ε=±0.087, δ=0.10. Observed coverage 88.3% within 5pp of 90% nominal.' },
                { step: '05', label: 'Recovery Proposed', desc: 'Rollback Embeddings Model to version v2.0. Policy gate: ALLOW. Execution mode: simulation.' },
              ].map((s, i) => (
                <div key={s.step} className={`flex gap-4 items-start py-4 ${i > 0 ? 'border-t border-[#0a0a0a]/10' : ''}`}>
                  <span className="font-mono text-[10px] text-[#888] w-8 flex-shrink-0">{s.step}</span>
                  <div>
                    <div className="font-mono text-xs font-bold text-[#0a0a0a] mb-1">{s.label}</div>
                    <div className="font-mono text-[10px] text-[#888] leading-relaxed">{s.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="mt-8 flex gap-4">
          <Link href="/recovery" className="font-mono text-[10px] tracking-widest uppercase border border-[#0a0a0a] px-6 py-2.5 bg-[#0a0a0a] text-[#ECEAE2] hover:bg-transparent hover:text-[#0a0a0a] transition-colors">
            → Recovery Console
          </Link>
          <Link href="/reports/r_987654321" className="font-mono text-[10px] tracking-widest uppercase border border-[#0a0a0a] px-6 py-2.5 hover:bg-[#0a0a0a] hover:text-[#ECEAE2] transition-colors">
            Full Report ↗
          </Link>
        </div>
      </div>
    </PageLayout>
  );
}
