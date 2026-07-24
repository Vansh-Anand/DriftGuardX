'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { format } from 'date-fns';
import { fetchRuns, Run } from '@/lib/api';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';

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

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Runs</h1>
          <p className="text-zinc-400">View and investigate pipeline executions.</p>
        </div>
      </div>

      <div className="rounded-xl border border-zinc-800 bg-black">
        {loading ? (
          <div className="p-12 flex justify-center"><Spinner className="w-8 h-8" /></div>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Status</TableHead>
                  <TableHead>ID</TableHead>
                  <TableHead>Time</TableHead>
                  <TableHead>Latency</TableHead>
                  <TableHead>Cost</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead>Tags</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.map(run => (
                  <TableRow key={run.id}>
                    <TableCell>
                      <Badge variant={run.status === 'stable' ? 'measured' : run.status === 'failed' ? 'destructive' : 'default'}>
                        {run.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      <Link href={`/runs/${run.id}`} className="text-blue-400 hover:underline">
                        {run.id.split('-')[0]}...
                      </Link>
                    </TableCell>
                    <TableCell className="text-zinc-300">
                      {format(new Date(run.created_at), 'MMM d, HH:mm:ss')}
                    </TableCell>
                    <TableCell>{run.total_latency_ms.toFixed(0)}ms</TableCell>
                    <TableCell>${run.total_cost_usd.toFixed(4)}</TableCell>
                    <TableCell>{run.reliability_score.toFixed(2)}</TableCell>
                    <TableCell>
                      {run.is_synthetic && <Badge variant="synthetic" className="mr-1">Synthetic</Badge>}
                    </TableCell>
                  </TableRow>
                ))}
                {runs.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center py-8 text-zinc-500">
                      No runs found.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
            
            <div className="flex items-center justify-between p-4 border-t border-zinc-800">
              <div className="text-sm text-zinc-400">
                Showing {Math.min((page - 1) * pageSize + 1, total)} to {Math.min(page * pageSize, total)} of {total} runs
              </div>
              <div className="flex gap-2">
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                >
                  Previous
                </Button>
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={() => setPage(p => p + 1)}
                  disabled={page * pageSize >= total}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
