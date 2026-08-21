'use client';

import { useState } from 'react';
import { Play } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import { Spinner } from '@/components/ui/spinner';
import { PageLayout } from '@/components/PageLayout';

const NODES = [
  { id: 'root', label: 'RAG Pipeline Root', x: '50%', y: '10%', tx: '-50%', key: 'root' },
  { id: 'rewriter', label: 'Query Rewriter', x: '20%', y: '42%', tx: '-50%', key: 'rewriter' },
  { id: 'retriever', label: 'Vector Retriever', x: '75%', y: '42%', tx: '-50%', key: 'retriever' },
  { id: 'embeddings', label: 'Embeddings Model', x: '75%', y: '78%', tx: '-50%', key: 'embeddings' },
];

export default function CausalGraphPage() {
  const [stage, setStage] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  const { toast } = useToast();

  const runDiagnostics = () => {
    setIsRunning(true);
    setStage(1);
    toast({ title: 'Diagnostics Started', description: 'Tracing execution graph and checking for drift...' });
    setTimeout(() => {
      setStage(2);
      setIsRunning(false);
      toast({ title: 'Drift Detected', description: 'Root cause: Embeddings Model version drift.', variant: 'destructive' });
    }, 2500);
  };

  const nodeStyle = (key: string) => {
    if (stage === 0) return { border: '1px solid #0a0a0a', background: '#ECEAE2', color: '#0a0a0a' };
    if (stage === 1) return { border: '1px solid #0a0a0a', background: '#0a0a0a', color: '#ECEAE2' };
    if (stage === 2) {
      if (key === 'retriever') return { border: '2px solid #dc2626', background: '#fef2f2', color: '#dc2626' };
      if (key === 'embeddings') return { border: '2px solid #f97316', background: '#fff7ed', color: '#c2410c' };
      if (key === 'root') return { border: '2px solid #dc2626', background: '#ECEAE2', color: '#dc2626' };
      return { border: '1px solid #0a0a0a', background: '#ECEAE2', color: '#0a0a0a' };
    }
    return {};
  };

  const scoreFor = (key: string) => {
    if (stage === 0) return key === 'root' ? '0.99' : key === 'rewriter' ? '0.98' : key === 'retriever' ? '0.97' : '0.99';
    if (stage === 1) return 'Testing...';
    if (key === 'root') return '0.65 ↓';
    if (key === 'rewriter') return '0.98';
    if (key === 'retriever') return '0.52 (Symptom)';
    if (key === 'embeddings') return '0.41 (Root Cause)';
    return '';
  };

  const badgeComp = (
    <div className="flex gap-3 items-center">
      <span className={`font-mono text-[10px] border px-3 py-1.5 tracking-widest uppercase ${stage === 2 ? 'border-red-600 text-red-600' : 'border-[#0a0a0a] text-[#0a0a0a]'}`}>
        {stage === 2 ? 'Drift Detected' : 'Scores Inferred'}
      </span>
      <button
        onClick={runDiagnostics}
        disabled={isRunning}
        className="flex items-center gap-2 font-mono text-[10px] tracking-widest uppercase border border-[#0a0a0a] px-4 py-1.5 hover:bg-[#0a0a0a] hover:text-[#ECEAE2] transition-colors disabled:opacity-40"
      >
        {isRunning ? <Spinner className="w-3 h-3" /> : <Play className="w-3 h-3" />}
        {isRunning ? 'Running...' : stage === 2 ? 'Re-run' : 'Run Diagnostics'}
      </button>
    </div>
  );

  return (
    <PageLayout title="Causal Graph" subtitle="Reliability attribution and drift propagation" badge={badgeComp}>
      <div className="p-8">
        <div className="border border-[#0a0a0a] relative overflow-hidden" style={{ height: 520 }}>
          {/* SVG edges */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ zIndex: 0 }}>
            <path d="M 50% 18% L 22% 40%" stroke={stage === 1 ? '#0a0a0a' : stage === 2 ? '#0a0a0a55' : '#0a0a0a33'} strokeWidth="1.5" fill="none" strokeDasharray={stage === 1 ? "4,4" : "none"} />
            <path d="M 50% 18% L 76% 40%" stroke={stage === 2 ? '#dc2626' : stage === 1 ? '#0a0a0a' : '#0a0a0a33'} strokeWidth={stage === 2 ? 2.5 : 1.5} fill="none" />
            <path d="M 76% 55% L 76% 76%" stroke={stage === 2 ? '#f97316' : stage === 1 ? '#0a0a0a' : '#0a0a0a33'} strokeWidth={stage === 2 ? 2.5 : 1.5} fill="none" />
          </svg>

          {/* Nodes */}
          {NODES.map((n) => (
            <div
              key={n.id}
              className="absolute w-52 p-4 transition-all duration-500"
              style={{ left: n.x, top: n.y, transform: `translateX(${n.tx})`, zIndex: 10, ...nodeStyle(n.key) }}
            >
              <div className="font-mono text-xs font-bold mb-1.5">{n.label}</div>
              <div className="font-mono text-[10px] opacity-60">Reliability: {scoreFor(n.key)}</div>
              {stage === 2 && n.key === 'embeddings' && (
                <div className="font-mono text-[10px] mt-2 border-t border-current pt-2 opacity-70">↑ Version drift detected</div>
              )}
            </div>
          ))}

          {/* Empty state */}
          {stage === 0 && (
            <div className="absolute bottom-6 left-1/2 -translate-x-1/2 font-mono text-xs text-[#888] text-center">
              Run diagnostics to trace attribution and detect drift
            </div>
          )}
        </div>

        {/* Legend */}
        <div className="flex gap-6 mt-4">
          <span className="font-mono text-[10px] text-[#888] flex items-center gap-2">
            <span className="w-4 h-[1px] bg-[#0a0a0a33] inline-block"/>Healthy path
          </span>
          <span className="font-mono text-[10px] text-red-500 flex items-center gap-2">
            <span className="w-4 h-[2px] bg-red-500 inline-block"/>Drift propagation
          </span>
          <span className="font-mono text-[10px] text-orange-500 flex items-center gap-2">
            <span className="w-4 h-[2px] bg-orange-500 inline-block"/>Root cause
          </span>
        </div>
      </div>
    </PageLayout>
  );
}
