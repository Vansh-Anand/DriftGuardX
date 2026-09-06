'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { format } from 'date-fns';
import { fetchRuns, Run } from '@/lib/api';
import { PageLayout } from '@/components/PageLayout';
import { Spinner } from '@/components/ui/spinner';

const STATUS_STYLE: Record<string, string> = {
  stable: 'border-[#0a0a0a] text-[#0a0a0a]',
  failed: 'border-red-600 text-red-600',
  default: 'border-[#888] text-[#888]',
};

export default function RunsPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 20;

  useEffect(() => {
    async function loadRuns() {
      setLoading(true);
      try {
        const data = await fetchRuns(page, pageSize);
        setRuns(data.runs);
        setTotal(data.total);
      } catch (err) {
        console.error("Failed to load runs", err);
      } finally {
        setLoading(false);
      }
    }
    loadRuns();
  }, [page]);

  const badge = (
    <span className="font-mono text-[10px] tracking-widest uppercase border border-[#0a0a0a] px-3 py-1.5">
      {total} Total
    </span>
  );

  return (
    <PageLayout title="Runs" subtitle="View and investigate pipeline executions" badge={badge}>
      <div className="p-8">
        {loading ? (
          <div className="flex justify-center p-12"><Spinner className="w-8 h-8" /></div>
        ) : (
          <div className="border border-[#0a0a0a]">
            {/* Table header */}
            <div className="grid grid-cols-[80px_1fr_140px_100px_90px_80px_100px] border-b border-[#0a0a0a] bg-[#0a0a0a] text-[#ECEAE2]">
              {["Status", "ID", "Time", "Latency", "Cost", "Score", "Tags"].map(h => (
                <div key={h} className="font-mono text-[10px] tracking-[0.15em] uppercase px-4 py-3">{h}</div>
              ))}
            </div>

            {runs.length === 0 ? (
              <div className="py-16 text-center font-mono text-xs text-[#888]">No runs found.</div>
            ) : runs.map((run, i) => (
              <div
                key={run.id}
                className={`grid grid-cols-[80px_1fr_140px_100px_90px_80px_100px] items-center ${i > 0 ? 'border-t border-[#0a0a0a]/10' : ''} hover:bg-[#0a0a0a]/5 transition-colors`}
              >
                <div className="px-4 py-3">
                  <span className={`font-mono text-[10px] border px-2 py-0.5 ${STATUS_STYLE[run.status] || STATUS_STYLE.default}`}>
                    {run.status?.toUpperCase()}
                  </span>
                </div>
                <div className="px-4 py-3 font-mono text-xs">
                  <Link href={`/runs/${run.id}`} className="text-[#0a0a0a] underline underline-offset-2 hover:opacity-60 transition-opacity">
                    {run.id.split('-')[0]}...
                  </Link>
                </div>
                <div className="px-4 py-3 font-mono text-xs text-[#888]">
                  {format(new Date(run.created_at), 'MMM d, HH:mm:ss')}
                </div>
                <div className="px-4 py-3 font-mono text-xs">{run.total_latency_ms.toFixed(0)}ms</div>
                <div className="px-4 py-3 font-mono text-xs">${run.total_cost_usd.toFixed(4)}</div>
                <div className="px-4 py-3 font-mono text-xs font-bold">{run.reliability_score.toFixed(2)}</div>
                <div className="px-4 py-3">
                  {run.evidence_class && (
                    <span className="font-mono text-[8px] border border-[#888] text-[#888] px-2 py-0.5">
                      {run.evidence_class.replace(/_/g, ' ')}
                    </span>
                  )}
                </div>
              </div>
            ))}

            {/* Pagination */}
            <div className="border-t border-[#0a0a0a] flex items-center justify-between px-4 py-3">
              <span className="font-mono text-[10px] text-[#888]">
                {Math.min((page - 1) * pageSize + 1, total)}–{Math.min(page * pageSize, total)} of {total}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="font-mono text-[10px] tracking-widest uppercase border border-[#0a0a0a] px-4 py-1.5 disabled:opacity-30 hover:bg-[#0a0a0a] hover:text-[#ECEAE2] transition-colors"
                >
                  ← Prev
                </button>
                <button
                  onClick={() => setPage(p => p + 1)}
                  disabled={page * pageSize >= total}
                  className="font-mono text-[10px] tracking-widest uppercase border border-[#0a0a0a] px-4 py-1.5 disabled:opacity-30 hover:bg-[#0a0a0a] hover:text-[#ECEAE2] transition-colors"
                >
                  Next →
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </PageLayout>
  );
}
