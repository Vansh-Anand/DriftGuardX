'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

export default function CausalGraphPage() {
  return (
    <div className="p-8 h-full flex flex-col">
      <div className="flex justify-between items-start mb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Causal Graph</h1>
          <p className="text-zinc-400">Reliability attribution and drift propagation</p>
        </div>
        <div className="flex gap-2">
          <Badge variant="inferred">Scores Inferred</Badge>
          <Button variant="outline">Export Layout</Button>
        </div>
      </div>

      <div className="flex-1 rounded-xl border border-zinc-800 bg-zinc-950/50 p-6 relative overflow-hidden flex items-center justify-center">
        {/* Mocking a Causal Graph using CSS/HTML structure instead of heavy D3 */}
        <div className="relative w-full max-w-4xl h-[500px]">
          
          {/* Nodes */}
          <div className="absolute top-10 left-1/2 -translate-x-1/2">
            <Card className="w-64 shadow-lg border-blue-900/50 bg-blue-950/20">
              <CardContent className="p-4">
                <div className="font-semibold text-blue-400 mb-1">RAG Pipeline Root</div>
                <div className="flex justify-between text-xs text-zinc-400">
                  <span>Reliability: 0.65</span>
                  <Badge variant="destructive" className="scale-75">Drift Detected</Badge>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="absolute top-48 left-1/4 -translate-x-1/2">
            <Card className="w-56">
              <CardContent className="p-4">
                <div className="font-semibold mb-1">Query Rewriter</div>
                <div className="text-xs text-zinc-400">Reliability: 0.98</div>
              </CardContent>
            </Card>
          </div>

          <div className="absolute top-48 right-1/4 translate-x-1/2">
            <Card className="w-56 border-red-900/50 bg-red-950/20">
              <CardContent className="p-4">
                <div className="font-semibold text-red-400 mb-1">Vector Retriever</div>
                <div className="text-xs text-zinc-400">Reliability: 0.52 (Symptom)</div>
              </CardContent>
            </Card>
          </div>

          <div className="absolute bottom-10 right-1/4 translate-x-1/2">
            <Card className="w-56 border-orange-900/50 bg-orange-950/20">
              <CardContent className="p-4">
                <div className="font-semibold text-orange-400 mb-1">Embeddings Model</div>
                <div className="text-xs text-zinc-400">Reliability: 0.41 (Root Cause)</div>
                <div className="mt-2 text-[10px] text-zinc-500 bg-black/50 p-1 rounded">Version drift detected</div>
              </CardContent>
            </Card>
          </div>

          {/* SVG Edges */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ zIndex: -1 }}>
            <path d="M 450 100 L 250 190" stroke="#3f3f46" strokeWidth="2" fill="none" strokeDasharray="5,5" />
            <path d="M 450 100 L 650 190" stroke="#7f1d1d" strokeWidth="3" fill="none" />
            <path d="M 650 250 L 650 420" stroke="#7f1d1d" strokeWidth="3" fill="none" />
          </svg>

        </div>
      </div>
    </div>
  );
}
