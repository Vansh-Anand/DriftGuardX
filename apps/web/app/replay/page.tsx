'use client';

import { useState } from 'react';
import { createReplay } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';

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
    <div className="p-8 max-w-4xl">
      <div className="mb-6">
        <h1 className="text-3xl font-bold tracking-tight">Replay Lab</h1>
        <p className="text-zinc-400">Budgeted counterfactual execution</p>
      </div>

      <Card className="mb-8">
        <CardHeader>
          <CardTitle>Launch Counterfactual Replay</CardTitle>
          <CardDescription>
            Select a target run and define the execution seed to deterministically replay the pipeline.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleReplay} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-1">Target Run ID</label>
              <input 
                type="text"
                value={runId}
                onChange={e => setRunId(e.target.value)}
                placeholder="e.g. 123e4567-e89b-12d3-a456-426614174000"
                className="w-full bg-zinc-900 border border-zinc-800 rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                required
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-1">Execution Seed (Determinism)</label>
              <input 
                type="number"
                value={seed}
                onChange={e => setSeed(Number(e.target.value))}
                className="w-full max-w-[200px] bg-zinc-900 border border-zinc-800 rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <Button type="submit" disabled={loading || !runId}>
              {loading ? <Spinner className="mr-2" /> : null}
              Trigger Replay Job
            </Button>
          </form>
        </CardContent>
      </Card>

      {error && (
        <div className="p-4 bg-red-900/20 border border-red-900 rounded-lg text-red-200 mb-8">
          <span className="font-bold">Error: </span> {error}
        </div>
      )}

      {result && (
        <Card>
          <CardHeader>
            <div className="flex justify-between items-start">
              <div>
                <CardTitle>Replay Job Enqueued</CardTitle>
                <CardDescription>The background orchestrator is processing the request.</CardDescription>
              </div>
              <Badge variant="inferred">Processing</Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="bg-zinc-950 border border-zinc-800 p-4 rounded-md font-mono text-sm text-zinc-300 overflow-x-auto">
              <pre>{JSON.stringify(result, null, 2)}</pre>
            </div>
          </CardContent>
        </Card>
      )}

    </div>
  );
}
