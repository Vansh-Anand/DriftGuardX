'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Spinner } from '@/components/ui/spinner';
import { fetchTelemetry, fetchProviders } from '@/lib/api';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export default function Home() {
  const [telemetry, setTelemetry] = useState<any>(null);
  const [providers, setProviders] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [telData, provData] = await Promise.all([
          fetchTelemetry(),
          fetchProviders()
        ]);
        setTelemetry(telData);
        setProviders(provData);
      } catch (err) {
        console.error("Failed to load overview data", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  // Mock time-series data for the chart
  const data = [
    { name: '00:00', traces: 120, latency: 150 },
    { name: '04:00', traces: 200, latency: 140 },
    { name: '08:00', traces: 150, latency: 160 },
    { name: '12:00', traces: 300, latency: 220 },
    { name: '16:00', traces: 250, latency: 180 },
    { name: '20:00', traces: 180, latency: 155 },
  ];

  if (loading) return <div className="p-12 flex justify-center"><Spinner className="w-8 h-8" /></div>;

  return (
    <main className="flex-1 p-8">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Overview</h1>
          <p className="text-zinc-400">System health and aggregated metrics</p>
        </div>
        <div className="flex gap-2">
          <Badge variant="certified">System Stable</Badge>
          <Badge variant="measured">Telemetry Active</Badge>
        </div>
      </div>

      <div className="bg-amber-500/10 border border-amber-500/20 rounded-md p-4 mb-8">
        <h3 className="text-amber-500 font-semibold mb-1">Confidential Research Prototype</h3>
        <p className="text-zinc-300 text-sm">
          This system is an experimental evaluation platform. Diagnoses and certificates represent statistical bounds calculated over measured graph topologies, not absolute causal guarantees or production safety certifications.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-zinc-400">Total Traces</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{telemetry?.metrics?.total_traces || 0}</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-zinc-400">Total Spans</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{telemetry?.metrics?.total_spans || 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-zinc-400">Errors</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-red-400">{telemetry?.metrics?.total_errors || 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-zinc-400">Ingestion Lag</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{telemetry?.metrics?.ingestion_lag_ms || 0}ms</div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <div className="md:col-span-2">
          <Card className="h-full">
            <CardHeader>
              <CardTitle>Trace Volume & Latency</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                    <XAxis dataKey="name" stroke="#888" />
                    <YAxis yAxisId="left" stroke="#888" />
                    <YAxis yAxisId="right" orientation="right" stroke="#888" />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#18181b', border: '1px solid #27272a' }}
                      itemStyle={{ color: '#e4e4e7' }}
                    />
                    <Line yAxisId="left" type="monotone" dataKey="traces" stroke="#3b82f6" strokeWidth={2} />
                    <Line yAxisId="right" type="monotone" dataKey="latency" stroke="#10b981" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </div>

        <div>
          <Card className="h-full">
            <CardHeader>
              <CardTitle>Providers</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {providers && Object.entries(providers).map(([name, config]: [string, any]) => (
                  <div key={name} className="flex justify-between items-center p-3 border border-zinc-800 rounded-lg">
                    <div>
                      <div className="font-semibold">{name}</div>
                      <div className="text-xs text-zinc-400">${config.cost_per_1k} / 1k tkns</div>
                    </div>
                    <Badge variant={config.status === 'healthy' ? 'measured' : 'destructive'}>
                      {config.status}
                    </Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </main>
  );
}
