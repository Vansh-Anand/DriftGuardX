'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Play } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import { Spinner } from '@/components/ui/spinner';

export default function CausalGraphPage() {
  const [isRunning, setIsRunning] = useState(false);
  const [stage, setStage] = useState(0); // 0: initial, 1: checking, 2: found drift
  const { toast } = useToast();

  const runDiagnostics = () => {
    setIsRunning(true);
    setStage(1);
    
    toast({
      title: 'Diagnostics Started',
      description: 'Tracing execution graph and checking for drift...',
    });

    setTimeout(() => {
      setStage(2);
      setIsRunning(false);
      toast({
        title: 'Drift Detected',
        description: 'Found root cause at the Embeddings Model.',
        variant: 'destructive'
      });
    }, 2500);
  };

  return (
    <div className="p-8 h-full flex flex-col">
      <div className="flex justify-between items-start mb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Causal Graph</h1>
          <p className="text-zinc-400">Reliability attribution and drift propagation</p>
        </div>
        <div className="flex gap-4">
          <Badge variant={stage === 2 ? 'destructive' : 'inferred'}>
            {stage === 2 ? 'Drift Detected' : 'Scores Inferred'}
          </Badge>
          <Button onClick={runDiagnostics} disabled={isRunning} variant="outline" className="bg-zinc-800 text-white hover:bg-zinc-700 hover:text-white">
            {isRunning ? <Spinner className="w-4 h-4 mr-2" /> : <Play className="w-4 h-4 mr-2" />}
            {isRunning ? 'Running...' : stage === 2 ? 'Re-run Diagnostics' : 'Run Diagnostics'}
          </Button>
        </div>
      </div>

      <div className="flex-1 rounded-xl border border-zinc-800 bg-zinc-950/50 p-6 relative overflow-hidden flex items-center justify-center">
        {/* Mocking a Causal Graph using CSS/HTML structure instead of heavy D3 */}
        <div className="relative w-full max-w-4xl h-[500px]">
          
          {/* Nodes */}
          <div className="absolute top-10 left-1/2 -translate-x-1/2 transition-transform duration-500 hover:scale-105 z-10">
            <Card className={`w-64 shadow-lg transition-colors duration-500 ${stage === 2 ? 'border-red-900/50 bg-red-950/20' : stage === 1 ? 'border-blue-500/50 bg-blue-950/20 animate-pulse' : 'border-blue-900/50 bg-blue-950/20'}`}>
              <CardContent className="p-4">
                <div className={`font-semibold mb-1 ${stage === 2 ? 'text-red-400' : 'text-blue-400'}`}>RAG Pipeline Root</div>
                <div className="flex justify-between text-xs text-zinc-400">
                  <span>Reliability: {stage === 2 ? '0.65' : stage === 1 ? 'Testing...' : '0.99'}</span>
                  {stage === 2 && <Badge variant="destructive" className="scale-75 animate-in zoom-in">Drift Detected</Badge>}
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="absolute top-48 left-1/4 -translate-x-1/2 transition-transform duration-500 hover:scale-105 z-10">
            <Card className={`w-56 transition-colors duration-500 ${stage === 1 ? 'border-blue-500/50 bg-blue-950/20 animate-pulse' : ''}`}>
              <CardContent className="p-4">
                <div className="font-semibold mb-1">Query Rewriter</div>
                <div className="text-xs text-zinc-400">Reliability: {stage === 1 ? 'Testing...' : '0.98'}</div>
              </CardContent>
            </Card>
          </div>

          <div className="absolute top-48 right-1/4 translate-x-1/2 transition-transform duration-500 hover:scale-105 z-10">
            <Card className={`w-56 transition-colors duration-500 ${stage === 2 ? 'border-red-900/50 bg-red-950/20' : stage === 1 ? 'border-blue-500/50 bg-blue-950/20 animate-pulse' : ''}`}>
              <CardContent className="p-4">
                <div className={`font-semibold mb-1 ${stage === 2 ? 'text-red-400' : ''}`}>Vector Retriever</div>
                <div className="text-xs text-zinc-400">Reliability: {stage === 2 ? '0.52 (Symptom)' : stage === 1 ? 'Testing...' : '0.97'}</div>
              </CardContent>
            </Card>
          </div>

          <div className="absolute bottom-10 right-1/4 translate-x-1/2 transition-transform duration-500 hover:scale-105 z-10">
            <Card className={`w-56 transition-colors duration-500 ${stage === 2 ? 'border-orange-900/50 bg-orange-950/20' : stage === 1 ? 'border-blue-500/50 bg-blue-950/20 animate-pulse delay-500' : ''}`}>
              <CardContent className="p-4">
                <div className={`font-semibold mb-1 ${stage === 2 ? 'text-orange-400' : ''}`}>Embeddings Model</div>
                <div className="text-xs text-zinc-400">Reliability: {stage === 2 ? '0.41 (Root Cause)' : stage === 1 ? 'Testing...' : '0.99'}</div>
                {stage === 2 && <div className="mt-2 text-[10px] text-zinc-500 bg-black/50 p-1 rounded animate-in fade-in slide-in-from-bottom-2">Version drift detected</div>}
              </CardContent>
            </Card>
          </div>

          {/* SVG Edges */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ zIndex: 0 }}>
            <path d="M 450 100 L 250 190" stroke={stage === 1 ? '#3b82f6' : '#3f3f46'} strokeWidth="2" fill="none" strokeDasharray="5,5" className={stage === 1 ? 'animate-pulse' : ''} />
            <path d="M 450 100 L 650 190" stroke={stage === 2 ? '#7f1d1d' : stage === 1 ? '#3b82f6' : '#3f3f46'} strokeWidth="3" fill="none" className={stage === 1 ? 'animate-pulse' : ''} />
            <path d="M 650 250 L 650 420" stroke={stage === 2 ? '#7f1d1d' : stage === 1 ? '#3b82f6' : '#3f3f46'} strokeWidth="3" fill="none" className={stage === 1 ? 'animate-pulse' : ''} />
          </svg>
        </div>
      </div>
    </div>
  );
}
