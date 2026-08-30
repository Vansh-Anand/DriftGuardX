'use client';
import Link from 'next/link';
import { PageLayout } from '@/components/PageLayout';

const REPORTS = [
  {
    run_id: 'r_987654321',
    status: 'CERTIFIED',
    evidence_kind: 'synthetic_simulation',
    action: 'Approve Rollback of Retriever to v1',
    epsilon: 0.087,
    confidence: '90%',
    trials: 35,
    created_at: '2026-07-22T14:30:00Z',
  },
  {
    run_id: 'r_123456789',
    status: 'UNCERTIFIED',
    evidence_kind: 'controlled_replay',
    action: 'Switch Generator Model',
    epsilon: null,
    confidence: '—',
    trials: 12,
    created_at: '2026-07-21T10:00:00Z',
  },
];

export default function ReportsIndexPage() {
  const badge = (
    <span className="font-mono text-[10px] border border-[#0a0a0a] px-3 py-1.5 uppercase tracking-widest">
      {REPORTS.length} Reports
    </span>
  );

  return (
    <PageLayout title="Diagnosis Reports" subtitle="Root cause analysis with Hoeffding statistical certification" badge={badge}>
      <div className="p-8">
        <div className="border border-[#0a0a0a]">
          <div className="grid grid-cols-[140px_1fr_120px_150px_120px_80px_120px] border-b border-[#0a0a0a] bg-[#0a0a0a] text-[#ECEAE2]">
            {['Run ID', 'Recommended Action', 'Status', 'Evidence', 'Confidence', 'Trials', ''].map(h => (
              <div key={h} className="font-mono text-[10px] tracking-[0.1em] uppercase px-4 py-3">{h}</div>
            ))}
          </div>
          {REPORTS.map((r, i) => (
            <div key={r.run_id} className={`grid grid-cols-[140px_1fr_120px_150px_120px_80px_120px] items-center ${i > 0 ? 'border-t border-[#0a0a0a]/10' : ''} hover:bg-[#0a0a0a]/5 transition-colors`}>
              <div className="px-4 py-4 font-mono text-[10px] text-[#0a0a0a]">{r.run_id}</div>
              <div className="px-4 py-4 font-mono text-xs">{r.action}</div>
              <div className="px-4 py-4">
                <span className={`font-mono text-[10px] border px-2 py-0.5 uppercase ${r.status === 'CERTIFIED' ? 'border-[#0a0a0a] text-[#0a0a0a]' : 'border-amber-500 text-amber-700'}`}>
                  {r.status}
                </span>
              </div>
              <div className="px-4 py-4 font-mono text-[10px] uppercase text-amber-700">
                {r.evidence_kind.replaceAll('_', ' ')}
              </div>
              <div className="px-4 py-4 font-mono text-xs">{r.confidence}</div>
              <div className="px-4 py-4 font-mono text-xs">N={r.trials}</div>
              <div className="px-4 py-4">
                <Link href={`/reports/${r.run_id}`} className="font-mono text-[10px] uppercase tracking-widest underline underline-offset-2 hover:opacity-60 transition-opacity">
                  View ↗
                </Link>
              </div>
            </div>
          ))}
        </div>
      </div>
    </PageLayout>
  );
}
