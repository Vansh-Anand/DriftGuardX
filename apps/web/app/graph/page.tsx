'use client';

import { useState } from 'react';
import { Play } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import { Spinner } from '@/components/ui/spinner';
import { PageLayout } from '@/components/PageLayout';
import { createRun, fetchRunTrace, TraceResponse } from '@/lib/api';

const DEFAULT_NODES = [
  { id: 'root', label: 'RAG Pipeline Root', x: '50%', y: '10%', tx: '-50%', key: 'root' },
  { id: 'policy', label: 'Policy Enforcer', x: '20%', y: '42%', tx: '-50%', key: 'policy' },
  { id: 'retriever', label: 'Vector Retriever', x: '75%', y: '42%', tx: '-50%', key: 'retriever' },
  { id: 'generator', label: 'LLM Generator', x: '75%', y: '78%', tx: '-50%', key: 'generator' },
];

export default function CausalGraphPage() {
  const [stage, setStage] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  const [traceData, setTraceData] = useState<TraceResponse | null>(null);
  const { toast } = useToast();

  const runDiagnostics = async () => {
    setIsRunning(true);
    setStage(1);
    toast({ title: 'Diagnostics Started', description: 'Executing pipeline trace...' });
    
    try {
      // 1. Create a real run against the FastAPI backend
      const run = await createRun("What is DriftGuard-X safety policy?");
      
      // 2. Fetch the real trace spans generated during the run
      const trace = await fetchRunTrace(run.id);
      
      if (trace) {
        setTraceData(trace);
        setStage(2);
        
        // Find if there are any errors in the trace spans
        const hasErrors = trace.spans.some(s => s.status_code === 'ERROR');
        
        if (hasErrors) {
          toast({ title: 'Drift Detected', description: 'Root cause identified in component trace.', variant: 'destructive' });
        } else {
          toast({ title: 'Diagnostics Complete', description: 'Pipeline is healthy.' });
        }
      }
    } catch (err) {
      console.error(err);
      toast({ title: 'Diagnostics Failed', description: 'Could not connect to FastAPI backend.', variant: 'destructive' });
      setStage(0);
    } finally {
      setIsRunning(false);
    }
  };

  const getSpanStatus = (key: string) => {
    if (!traceData) return 'UNKNOWN';
    // Map UI keys to backend span names/components roughly
    let span = null;
    if (key === 'root') span = traceData.spans.find(s => s.name === 'rag_pipeline_run');
    if (key === 'policy') span = traceData.spans.find(s => s.name === 'policy_check');
    if (key === 'retriever') span = traceData.spans.find(s => s.name === 'retrieve');
    if (key === 'generator') span = traceData.spans.find(s => s.name === 'llm_generate');
    
    return span ? span.status_code : 'OK';
  };

  const getSpanLatency = (key: string) => {
    if (!traceData) return null;
    let span = null;
    if (key === 'root') span = traceData.spans.find(s => s.name === 'rag_pipeline_run');
    if (key === 'policy') span = traceData.spans.find(s => s.name === 'policy_check');
    if (key === 'retriever') span = traceData.spans.find(s => s.name === 'retrieve');
    if (key === 'generator') span = traceData.spans.find(s => s.name === 'llm_generate');
    
    return span?.latency_ms;
  };

  const nodeStyle = (key: string) => {
    if (stage === 0) return { border: '1px solid #0a0a0a', background: '#ECEAE2', color: '#0a0a0a' };
    if (stage === 1) return { border: '1px solid #0a0a0a', background: '#0a0a0a', color: '#ECEAE2' };
    if (stage === 2) {
      const status = getSpanStatus(key);
      if (status === 'ERROR') {
        if (key === 'retriever' || key === 'generator') return { border: '2px solid #f97316', background: '#fff7ed', color: '#c2410c' }; // Root cause
        return { border: '2px solid #dc2626', background: '#fef2f2', color: '#dc2626' }; // Propagation
      }
      return { border: '1px solid #0a0a0a', background: '#ECEAE2', color: '#0a0a0a' }; // Healthy
    }
    return {};
  };

  const scoreFor = (key: string) => {
    if (stage === 0) return '0.99';
    if (stage === 1) return 'Testing...';
    
    const latency = getSpanLatency(key);
    const status = getSpanStatus(key);
    
    if (status === 'ERROR') {
      return `Failed (${latency}ms)`;
    }
    
    return latency ? `OK (${latency}ms)` : 'OK';
  };

  const isHealthyPath = stage === 2 && !traceData?.spans.some(s => s.status_code === 'ERROR');

  const badgeComp = (
    <div className="flex gap-3 items-center">
      <span className={`font-mono text-[10px] border px-3 py-1.5 tracking-widest uppercase ${stage === 2 && !isHealthyPath ? 'border-red-600 text-red-600' : 'border-[#0a0a0a] text-[#0a0a0a]'}`}>
        {stage === 2 ? (isHealthyPath ? 'Healthy' : 'Drift Detected') : 'Scores Inferred'}
      </span>
      <button
        onClick={runDiagnostics}
        disabled={isRunning}
        className="flex items-center gap-2 font-mono text-[10px] tracking-widest uppercase border border-[#0a0a0a] px-4 py-1.5 hover:bg-[#0a0a0a] hover:text-[#ECEAE2] transition-colors disabled:opacity-40"
      >
        {isRunning ? <Spinner className="w-3 h-3" /> : <Play className="w-3 h-3" />}
        {isRunning ? 'Running API...' : stage === 2 ? 'Re-run via API' : 'Run Diagnostics'}
      </button>
    </div>
  );

  return (
    <PageLayout title="Causal Graph" subtitle="Reliability attribution and drift propagation" badge={badgeComp}>
      <div className="p-8">
        <div className="border border-[#0a0a0a] relative overflow-hidden" style={{ height: 520 }}>
          {/* SVG edges */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ zIndex: 0 }}>
            <path d="M 50% 18% L 22% 40%" stroke={stage === 1 ? '#0a0a0a' : (stage === 2 && getSpanStatus('policy') === 'ERROR') ? '#dc2626' : '#0a0a0a33'} strokeWidth={stage === 2 && getSpanStatus('policy') === 'ERROR' ? 2.5 : 1.5} fill="none" strokeDasharray={stage === 1 ? "4,4" : "none"} />
            <path d="M 50% 18% L 76% 40%" stroke={stage === 2 && getSpanStatus('retriever') === 'ERROR' ? '#dc2626' : stage === 1 ? '#0a0a0a' : '#0a0a0a33'} strokeWidth={stage === 2 && getSpanStatus('retriever') === 'ERROR' ? 2.5 : 1.5} fill="none" />
            <path d="M 76% 55% L 76% 76%" stroke={stage === 2 && getSpanStatus('generator') === 'ERROR' ? '#f97316' : stage === 1 ? '#0a0a0a' : '#0a0a0a33'} strokeWidth={stage === 2 && getSpanStatus('generator') === 'ERROR' ? 2.5 : 1.5} fill="none" />
          </svg>

          {/* Nodes */}
          {DEFAULT_NODES.map((n) => (
            <div
              key={n.id}
              className="absolute w-52 p-4 transition-all duration-500"
              style={{ left: n.x, top: n.y, transform: `translateX(${n.tx})`, zIndex: 10, ...nodeStyle(n.key) }}
            >
              <div className="font-mono text-xs font-bold mb-1.5">{n.label}</div>
              <div className="font-mono text-[10px] opacity-60">Status: {scoreFor(n.key)}</div>
              {stage === 2 && getSpanStatus(n.key) === 'ERROR' && (n.key === 'retriever' || n.key === 'generator') && (
                <div className="font-mono text-[10px] mt-2 border-t border-current pt-2 opacity-70">↑ Upstream fault detected</div>
              )}
            </div>
          ))}

          {/* Empty state */}
          {stage === 0 && (
            <div className="absolute bottom-6 left-1/2 -translate-x-1/2 font-mono text-xs text-[#888] text-center">
              Run diagnostics to trace attribution using the real FastAPI backend
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
