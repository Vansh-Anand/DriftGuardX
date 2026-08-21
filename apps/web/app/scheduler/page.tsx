'use client';
import { PageLayout } from '@/components/PageLayout';
import Link from 'next/link';

const ARMS = [
  { id: 'arm_1', name: 'Decrease Temperature (0.1)', gain: 0.15, cost: 0.05, active: true },
  { id: 'arm_2', name: 'Switch to GPT-4', gain: 0.85, cost: 0.80, active: false },
  { id: 'arm_3', name: 'Enable Dense Retrieval', gain: 0.40, cost: 0.20, active: true },
];

export default function SchedulerPage() {
  const badge = (
    <span className="font-mono text-[10px] border border-[#0a0a0a] px-3 py-1.5 uppercase tracking-widest">
      Budget: $5.00 / $10.00
    </span>
  );

  return (
    <PageLayout title="BCRB Scheduler" subtitle="Budgeted Contextual Multi-Armed Bandit Evaluation" badge={badge}>
      <div className="p-8">
        {/* Stat row */}
        <div className="grid grid-cols-3 border border-[#0a0a0a] mb-8">
          <div className="p-6">
            <div className="font-mono text-[10px] tracking-[0.15em] uppercase text-[#888] mb-3">Information Gain</div>
            <div className="font-sans font-bold text-4xl tracking-tight text-[#0a0a0a]">+1.24</div>
            <div className="font-mono text-xs text-[#888] mt-1">nats</div>
          </div>
          <div className="border-l border-[#0a0a0a] p-6">
            <div className="font-mono text-[10px] tracking-[0.15em] uppercase text-[#888] mb-3">Confidence Interval</div>
            <div className="font-sans font-bold text-4xl tracking-tight text-[#0a0a0a]">[0.85, 0.92]</div>
          </div>
          <div className="border-l border-[#0a0a0a] p-6">
            <div className="font-mono text-[10px] tracking-[0.15em] uppercase text-[#888] mb-3">Stop Reason</div>
            <div className="font-sans font-bold text-2xl tracking-tight text-[#0a0a0a]">Target Achieved</div>
            <div className="font-mono text-xs text-[#888] mt-1">Convergence criterion met</div>
          </div>
        </div>

        {/* Budget bar */}
        <div className="border border-[#0a0a0a] p-6 mb-8">
          <div className="flex justify-between mb-2">
            <span className="font-mono text-[10px] uppercase tracking-widest text-[#888]">Compute Budget</span>
            <span className="font-mono text-[10px] text-[#0a0a0a]">$5.00 / $10.00 (50%)</span>
          </div>
          <div className="w-full h-2 border border-[#0a0a0a] bg-transparent">
            <div className="h-full bg-[#0a0a0a]" style={{ width: '50%' }} />
          </div>
        </div>

        {/* Arms table */}
        <div className="border border-[#0a0a0a]">
          <div className="font-mono text-xs tracking-[0.15em] uppercase text-[#888] px-6 py-4 border-b border-[#0a0a0a]">
            Candidate Arms
          </div>
          {/* Header */}
          <div className="grid grid-cols-[80px_1fr_160px_120px_120px] border-b border-[#0a0a0a] bg-[#0a0a0a] text-[#ECEAE2]">
            {['Status', 'Intervention', 'Exp. Gain (nats)', 'Est. Cost', 'Action'].map(h => (
              <div key={h} className="font-mono text-[10px] tracking-[0.1em] uppercase px-4 py-3">{h}</div>
            ))}
          </div>
          {ARMS.map((arm, i) => (
            <div key={arm.id} className={`grid grid-cols-[80px_1fr_160px_120px_120px] items-center ${i > 0 ? 'border-t border-[#0a0a0a]/10' : ''} hover:bg-[#0a0a0a]/5 transition-colors`}>
              <div className="px-4 py-4">
                <span className={`font-mono text-[10px] border px-2 py-0.5 uppercase tracking-wider ${arm.active ? 'border-[#0a0a0a] text-[#0a0a0a]' : 'border-[#888] text-[#888]'}`}>
                  {arm.active ? 'Selected' : 'Pruned'}
                </span>
              </div>
              <div className="px-4 py-4 font-mono text-xs text-[#0a0a0a]">{arm.name}</div>
              <div className="px-4 py-4 font-mono text-xs font-bold">{arm.gain.toFixed(2)}</div>
              <div className="px-4 py-4 font-mono text-xs">${arm.cost.toFixed(2)}</div>
              <div className="px-4 py-4">
                <Link href={`/scheduler/${arm.id}`} className="font-mono text-[10px] uppercase tracking-widest underline underline-offset-2 hover:opacity-60 transition-opacity">
                  Details ↗
                </Link>
              </div>
            </div>
          ))}
        </div>
      </div>
    </PageLayout>
  );
}
