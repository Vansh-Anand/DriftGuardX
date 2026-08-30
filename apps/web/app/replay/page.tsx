'use client';

import { useState } from 'react';
import { createReplay } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { PageLayout } from '@/components/PageLayout';

export default function ReplayLabPage() {
  const [runId, setRunId] = useState('');
  const [seed, setSeed] = useState(42);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');

  const handleReplay = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!runId) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const res = await createReplay(runId, seed);
      setResult(res);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <PageLayout title="Replay Lab" subtitle="Budget-constrained counterfactual execution">
      <div className="p-8">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Form */}
          <div className="border border-[#0a0a0a] p-6">
            <div className="font-mono text-xs tracking-[0.15em] uppercase text-[#888] mb-6">Launch Counterfactual Replay</div>
            <p className="font-mono text-xs text-[#888] mb-6 leading-relaxed">
              Select a target run and define the execution seed to deterministically replay the pipeline with a new intervention hypothesis.
            </p>
            <form onSubmit={handleReplay} className="space-y-6">
              <div>
                <label className="font-mono text-[10px] tracking-widest uppercase text-[#888] block mb-2">Target Run ID</label>
                <input
                  type="text"
                  value={runId}
                  onChange={e => setRunId(e.target.value)}
                  placeholder="e.g. 123e4567-e89b-12d3-a456-426614174000"
                  className="w-full border border-[#0a0a0a] bg-transparent px-3 py-2.5 font-mono text-xs text-[#0a0a0a] placeholder:text-[#888] focus:outline-none focus:ring-1 focus:ring-[#0a0a0a]"
                  required
                />
              </div>
              <div>
                <label className="font-mono text-[10px] tracking-widest uppercase text-[#888] block mb-2">Execution Seed (Determinism)</label>
                <input
                  type="number"
                  value={seed}
                  onChange={e => setSeed(Number(e.target.value))}
                  className="w-36 border border-[#0a0a0a] bg-transparent px-3 py-2.5 font-mono text-xs text-[#0a0a0a] focus:outline-none focus:ring-1 focus:ring-[#0a0a0a]"
                />
              </div>
              <button
                type="submit"
                disabled={loading || !runId}
                className="flex items-center gap-2 font-mono text-[10px] tracking-widest uppercase border border-[#0a0a0a] px-6 py-2.5 bg-[#0a0a0a] text-[#ECEAE2] hover:bg-transparent hover:text-[#0a0a0a] transition-colors disabled:opacity-40"
              >
                {loading ? <Spinner className="w-3 h-3" /> : null}
                Trigger Replay Job
              </button>
            </form>

            {error && (
              <div className="mt-6 border border-red-500 border-l-4 border-l-red-500 p-4 font-mono text-xs text-red-700">
                <strong>Error:</strong> {error}
              </div>
            )}
          </div>

          {/* Info panel */}
          <div className="border border-[#0a0a0a] p-6">
            <div className="font-mono text-xs tracking-[0.15em] uppercase text-[#888] mb-6">How It Works</div>
            <div className="space-y-5">
              {[
                ['01', 'Seed-Pinned', 'Replay uses a fixed random seed to ensure deterministic component selection and ordering across trial runs.'],
                ['02', 'Budget-Bounded', 'The BCRB Scheduler enforces a hard $10.00 compute budget. Trials are halted when the budget is exhausted.'],
                ['03', 'Process-Isolated', 'Every replay crosses a killable process or container boundary with incremental time, memory, and output enforcement.'],
                ['04', 'Policy-Gated', 'All replay actions are subject to pre-execution policy checks before any state mutations occur.'],
              ].map(([num, title, desc]) => (
                <div key={num} className="border-t border-[#0a0a0a]/10 pt-4 grid grid-cols-[30px_1fr] gap-3">
                  <span className="font-mono text-xs text-[#888]">{num}</span>
                  <div>
                    <div className="font-mono text-xs font-bold text-[#0a0a0a] mb-1">{title}</div>
                    <div className="font-mono text-[10px] text-[#888] leading-relaxed">{desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Result */}
        {result && (
          <div className="mt-8 border border-[#0a0a0a] p-6">
            <div className="flex justify-between items-center mb-4">
              <div className="font-mono text-xs tracking-[0.15em] uppercase text-[#888]">Replay Job Enqueued</div>
              <span className="font-mono text-[10px] border border-[#0a0a0a] px-3 py-1 uppercase tracking-widest">Processing</span>
            </div>
            <pre className="font-mono text-xs text-[#0a0a0a] bg-[#0a0a0a]/5 border border-[#0a0a0a]/20 p-4 overflow-x-auto leading-relaxed">
              {JSON.stringify(result, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </PageLayout>
  );
}
