'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { format } from 'date-fns';
import { fetchRun, fetchRunTrace, Run, TraceResponse } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Spinner } from '@/components/ui/spinner';
import { Button } from '@/components/ui/button';

export default function RunDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [run, setRun] = useState<Run | null>(null);
  const [trace, setTrace] = useState<TraceResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [runData, traceData] = await Promise.all([
          fetchRun(id),
          fetchRunTrace(id).catch(() => null)
        ]);
        setRun(runData);
        setTrace(traceData);
      } catch (err) {
        console.error("Failed to load run details", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [id]);

  if (loading) return <div className="p-12 flex justify-center"><Spinner className="w-8 h-8" /></div>;
  if (!run) return <div className="p-12 text-center text-zinc-400">Run not found.</div>;

  return (
    <div className="p-8">
      <div className="flex justify-between items-start mb-6">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-3xl font-bold tracking-tight">Run Details</h1>
            <Badge variant={run.status === 'stable' ? 'measured' : run.status === 'failed' ? 'destructive' : 'default'}>
              {run.status}
            </Badge>
            {run.evidence_class && (
              <Badge variant="outline" className="border-zinc-500 text-zinc-500 font-mono text-[10px]">
                {run.evidence_class.replace(/_/g, ' ')}
              </Badge>
            )}
          </div>
          <p className="text-zinc-400 font-mono text-sm">{run.id}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline">View Causal Graph</Button>
          <Button variant="outline">View Trace Timeline</Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-zinc-400">Execution Time</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold">{format(new Date(run.created_at), 'MMM d, HH:mm:ss')}</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-zinc-400">Total Latency</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold">{run.total_latency_ms.toFixed(0)}ms</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-zinc-400">Total Tokens</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold">{run.total_tokens}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-zinc-400">Reliability Score</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold">{run.reliability_score.toFixed(2)}</div>
          </CardContent>
        </Card>
      </div>

      <Card className="mb-8">
        <CardHeader>
          <CardTitle>Error Information</CardTitle>
        </CardHeader>
        <CardContent>
          {run.error_type ? (
            <div className="p-4 bg-red-900/20 border border-red-900 rounded-lg">
              <h4 className="font-semibold text-red-400 mb-1">{run.error_type}</h4>
              <p className="text-red-200/80 text-sm">{run.error_message}</p>
            </div>
          ) : (
            <p className="text-zinc-400">No errors recorded for this run.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Trace Summary</CardTitle>
        </CardHeader>
        <CardContent>
          {trace ? (
            <div>
              <p className="text-zinc-300 mb-4">Total Spans: {trace.total_span_count}</p>
              <div className="space-y-2">
                {trace.spans.map((span) => (
                  <div key={span.span_id} className="p-3 border border-zinc-800 rounded flex justify-between items-center bg-zinc-900/50">
                    <div>
                      <span className="font-semibold">{span.name}</span>
                      <span className="text-xs text-zinc-500 ml-2 font-mono">{span.component_type || span.kind}</span>
                    </div>
                    <div className="flex gap-4 items-center">
                      <span className="text-sm">{span.latency_ms?.toFixed(0)}ms</span>
                      <Badge variant={span.status_code === 'ERROR' ? 'destructive' : 'outline'}>{span.status_code}</Badge>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-zinc-400">Trace data unavailable.</p>
          )}
        </CardContent>
      </Card>

    </div>
  );
}
