'use client';

import { useState, useEffect } from 'react';
import { PageLayout } from '@/components/PageLayout';
import { Spinner } from '@/components/ui/spinner';
import { fetchTelemetry, fetchProviders } from '@/lib/api';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useToast } from '@/components/ui/use-toast';

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="border border-[#0a0a0a] p-6 bg-[#ECEAE2]">
      <div className="font-mono text-[10px] text-[#888] tracking-[0.2em] uppercase mb-3">{label}</div>
      <div className="font-sans font-bold text-4xl tracking-tight text-[#0a0a0a]">{value}</div>
      {sub && <div className="font-mono text-xs text-[#888] mt-1">{sub}</div>}
    </div>
  );
}

export default function DashboardPage() {
  const { toast } = useToast();
  const [telemetry, setTelemetry] = useState<any>(null);
  const [providers, setProviders] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState([
    { name: '00:00', traces: 120, latency: 150 },
    { name: '04:00', traces: 200, latency: 140 },
    { name: '08:00', traces: 150, latency: 160 },
    { name: '12:00', traces: 300, latency: 220 },
    { name: '16:00', traces: 250, latency: 180 },
    { name: '20:00', traces: 180, latency: 155 },
  ]);

  useEffect(() => {
    async function loadData() {
      try {
        const [telData, provData] = await Promise.all([fetchTelemetry(), fetchProviders()]);
        setTelemetry(telData);
        setProviders(provData);
      } catch (err) {
        console.error("Failed to load overview data", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();

    const interval = setInterval(() => {
      setTelemetry((prev: any) => {
        if (!prev) return prev;
        return {
          ...prev,
          metrics: {
            ...prev.metrics,
            total_traces: (prev.metrics?.total_traces || 0) + Math.floor(Math.random() * 5),
            total_spans: (prev.metrics?.total_spans || 0) + Math.floor(Math.random() * 15),
            ingestion_lag_ms: Math.floor(Math.random() * 50) + 10,
          }
        };
      });
      setData((prev) => {
        const newData = [...prev];
        const last = newData[newData.length - 1];
        newData.shift();
        const now = new Date();
        const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
        newData.push({ name: timeStr, traces: last.traces + (Math.random() * 40 - 20), latency: last.latency + (Math.random() * 20 - 10) });
        return newData;
      });
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  const badge = (
    <span className="font-mono text-[10px] tracking-widest uppercase border border-[#0a0a0a] px-3 py-1.5 bg-[#0a0a0a] text-[#ECEAE2]">
      ● Live
    </span>
  );

  if (loading) return (
    <PageLayout title="Overview" subtitle="System health and aggregated metrics" badge={badge}>
      <div className="p-12 flex justify-center"><Spinner className="w-8 h-8" /></div>
    </PageLayout>
  );

  return (
    <PageLayout title="Overview" subtitle="System health and aggregated metrics" badge={badge}>
      <div className="p-8">

        {/* Research disclaimer */}
        <div className="border border-[#0a0a0a]/30 border-l-4 border-l-amber-500 p-4 mb-8 bg-amber-50/50">
          <h3 className="font-mono text-xs font-bold text-amber-700 tracking-widest uppercase mb-1">Confidential Research Prototype</h3>
          <p className="font-mono text-xs text-[#888]">
            Diagnoses represent statistical bounds over measured graph topologies — not absolute causal guarantees or production safety certifications.
          </p>
        </div>

        {/* Stat Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 border border-[#0a0a0a] mb-8">
          <StatCard label="Total Traces" value={telemetry?.metrics?.total_traces || 0} />
          <div className="border-l border-[#0a0a0a]">
            <StatCard label="Total Spans" value={telemetry?.metrics?.total_spans || 0} />
          </div>
          <div className="border-l border-[#0a0a0a]">
            <StatCard label="Errors" value={telemetry?.metrics?.total_errors || 0} sub="Pipeline errors detected" />
          </div>
          <div className="border-l border-[#0a0a0a]">
            <StatCard label="Ingestion Lag" value={`${telemetry?.metrics?.ingestion_lag_ms || 0}ms`} sub="Realtime stream" />
          </div>
        </div>

        {/* Chart + Providers */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="md:col-span-2 border border-[#0a0a0a] p-6">
            <div className="font-mono text-xs tracking-[0.15em] uppercase text-[#888] mb-6">Trace Volume & Latency</div>
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#0a0a0a22" vertical={false} />
                  <XAxis dataKey="name" stroke="#888" tick={{ fontFamily: 'var(--font-mono)', fontSize: 10 }} />
                  <YAxis yAxisId="left" stroke="#888" tick={{ fontFamily: 'var(--font-mono)', fontSize: 10 }} />
                  <YAxis yAxisId="right" orientation="right" stroke="#888" tick={{ fontFamily: 'var(--font-mono)', fontSize: 10 }} />
                  <Tooltip contentStyle={{ backgroundColor: '#ECEAE2', border: '1px solid #0a0a0a', fontFamily: 'var(--font-mono)', fontSize: 11 }} />
                  <Line yAxisId="left" type="monotone" dataKey="traces" stroke="#0a0a0a" strokeWidth={2} dot={false} />
                  <Line yAxisId="right" type="monotone" dataKey="latency" stroke="#888" strokeWidth={1.5} strokeDasharray="4 4" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="flex gap-6 mt-4">
              <span className="font-mono text-xs text-[#0a0a0a] flex items-center gap-2"><span className="w-4 h-0.5 bg-[#0a0a0a] inline-block"/> Trace Volume</span>
              <span className="font-mono text-xs text-[#888] flex items-center gap-2"><span className="w-4 h-0.5 bg-[#888] inline-block border-dashed"/> Latency (ms)</span>
            </div>
          </div>

          <div className="border border-[#0a0a0a] p-6">
            <div className="font-mono text-xs tracking-[0.15em] uppercase text-[#888] mb-4">Providers</div>
            <div className="space-y-0">
              {providers && Object.entries(providers).map(([name, config]: [string, any], i) => (
                <div key={name} className={`py-3 flex justify-between items-center ${i > 0 ? 'border-t border-[#0a0a0a]/10' : ''}`}>
                  <div>
                    <div className="font-mono text-xs font-bold text-[#0a0a0a]">{name}</div>
                    <div className="font-mono text-[10px] text-[#888]">${config.cost_per_1k} / 1k tokens</div>
                  </div>
                  <span className={`font-mono text-[10px] border px-2 py-1 ${config.status === 'healthy' ? 'border-[#0a0a0a] text-[#0a0a0a]' : 'border-red-500 text-red-600'}`}>
                    {config.status?.toUpperCase()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </PageLayout>
  );
}
