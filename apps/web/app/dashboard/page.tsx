'use client';

import { useEffect, useState } from 'react';
import { Activity, DatabaseZap, Layers3, Radio, ShieldCheck, TriangleAlert, type LucideIcon } from 'lucide-react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { PageLayout } from '@/components/PageLayout';
import { Spinner } from '@/components/ui/spinner';
import { fetchProviders, fetchTelemetry } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';

type Telemetry = {
  metrics?: {
    total_traces?: number;
    total_spans?: number;
    total_errors?: number;
    ingestion_lag_ms?: number;
  };
};

type Provider = { cost_per_1k?: number; status?: string };
type Providers = Record<string, Provider>;

const TREND = [
  { name: '00:00', traces: 120, latency: 150 },
  { name: '04:00', traces: 200, latency: 140 },
  { name: '08:00', traces: 150, latency: 160 },
  { name: '12:00', traces: 300, latency: 220 },
  { name: '16:00', traces: 250, latency: 180 },
  { name: '20:00', traces: 180, latency: 155 },
];

function StatCard({ icon: Icon, label, value, sub, signal = false }: {
  icon: LucideIcon;
  label: string;
  value: string | number;
  sub: string;
  signal?: boolean;
}) {
  return (
    <div className="glass-panel group relative overflow-hidden rounded-2xl p-5 transition-transform duration-300 hover:-translate-y-1">
      <div className="absolute -right-8 -top-8 h-24 w-24 rounded-full bg-[#7cf7d4]/5 blur-2xl transition-colors group-hover:bg-[#7cf7d4]/10" />
      <div className="flex items-center justify-between">
        <span className="font-mono text-[9px] uppercase tracking-[.2em] text-[#789b90]">{label}</span>
        <span className="grid h-8 w-8 place-items-center rounded-xl border border-[#b7ffe5]/10 bg-[#b7ffe5]/5 text-[#7cf7d4]">
          <Icon size={14} />
        </span>
      </div>
      <div className="mt-5 flex items-end gap-2">
        <span className="text-4xl font-semibold tracking-[-.05em] text-[#effff9]">{value}</span>
        {signal && <span className="mb-2 h-1.5 w-1.5 rounded-full bg-[#7cf7d4] signal-dot animate-signal" />}
      </div>
      <div className="mt-2 font-mono text-[10px] text-[#67877d]">{sub}</div>
    </div>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [providers, setProviders] = useState<Providers | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    async function loadData() {
      try {
        const [telemetryResult, providerResult] = await Promise.all([fetchTelemetry(), fetchProviders()]);
        if (active) {
          setTelemetry(telemetryResult as Telemetry);
          setProviders(providerResult as Providers);
        }
      } catch (error) {
        console.error('Failed to load authenticated overview data', error);
      } finally {
        if (active) setLoading(false);
      }
    }
    void loadData();
    return () => { active = false; };
  }, [user]);

  const connected = Boolean(telemetry);
  const badge = (
    <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 font-mono text-[9px] uppercase tracking-[.16em] ${connected ? 'border-[#7cf7d4]/30 bg-[#7cf7d4]/10 text-[#7cf7d4]' : 'border-amber-300/25 bg-amber-300/10 text-amber-200'}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${connected ? 'bg-[#7cf7d4] signal-dot animate-signal' : 'bg-amber-200'}`} />
      {connected ? 'Authenticated stream' : 'Awaiting telemetry'}
    </span>
  );

  if (loading) {
    return (
      <PageLayout title="Overview" subtitle="Evidence-aware system health and reliability signals" badge={badge}>
        <div className="grid min-h-[60vh] place-items-center"><Spinner className="h-8 w-8 text-[#7cf7d4]" /></div>
      </PageLayout>
    );
  }

  const metrics = telemetry?.metrics;
  const providerEntries = Object.entries(providers ?? {});

  return (
    <PageLayout title="Overview" subtitle="Evidence-aware system health and reliability signals" badge={badge}>
      <div className="mx-auto max-w-[1500px] space-y-6 p-4 md:p-8">
        <section className="glass-panel relative overflow-hidden rounded-3xl p-6 md:p-8">
          <div className="absolute right-0 top-0 h-64 w-64 rounded-full bg-[#9b87ff]/10 blur-[100px]" />
          <div className="relative grid gap-8 xl:grid-cols-[1.35fr_.65fr] xl:items-end">
            <div>
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-[#9b87ff]/25 bg-[#9b87ff]/10 px-3 py-1 font-mono text-[9px] uppercase tracking-[.18em] text-[#c7bbff]">
                <ShieldCheck size={12} /> Research evidence boundary active
              </div>
              <h2 className="max-w-3xl text-3xl font-semibold leading-[1.05] tracking-[-.04em] text-[#effff9] md:text-5xl">
                See the failure path.<br /><span className="text-[#7cf7d4]">Prove the recovery path.</span>
              </h2>
              <p className="mt-4 max-w-2xl font-mono text-[11px] leading-6 text-[#83a49a]">
                Every diagnosis stays attached to its evidence class. Synthetic evaluations cannot silently become replay or production claims.
              </p>
            </div>
            <div className="grid grid-cols-3 gap-2 rounded-2xl border border-[#b7ffe5]/10 bg-black/15 p-3">
              {['Trace', 'Replay', 'Certify'].map((step, index) => (
                <div key={step} className="relative rounded-xl border border-[#b7ffe5]/10 bg-[#b7ffe5]/[.03] px-3 py-4 text-center">
                  <div className="font-mono text-[9px] text-[#55766c]">0{index + 1}</div>
                  <div className="mt-1 text-xs font-medium text-[#dff8ef]">{step}</div>
                  {index < 2 && <span className="absolute -right-2 top-1/2 z-10 text-[#7cf7d4]">→</span>}
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard icon={Activity} label="Total traces" value={metrics?.total_traces ?? '—'} sub={connected ? 'Tenant-scoped executions' : 'Sign in to connect'} signal={connected} />
          <StatCard icon={Layers3} label="Total spans" value={metrics?.total_spans ?? '—'} sub="Versioned causal observations" />
          <StatCard icon={TriangleAlert} label="Detected errors" value={metrics?.total_errors ?? '—'} sub="Measured pipeline events" />
          <StatCard icon={Radio} label="Ingestion lag" value={metrics ? `${metrics.ingestion_lag_ms ?? 0}ms` : '—'} sub="Authenticated stream latency" />
        </section>

        <section className="grid gap-6 xl:grid-cols-[1.45fr_.55fr]">
          <div className="glass-panel rounded-3xl p-5 md:p-7">
            <div className="mb-8 flex items-start justify-between gap-4">
              <div>
                <div className="font-mono text-[9px] uppercase tracking-[.2em] text-[#789b90]">Signal topology</div>
                <h3 className="mt-2 text-xl font-medium text-[#effff9]">Trace volume and latency envelope</h3>
              </div>
              <span className="rounded-full border border-[#b7ffe5]/10 px-3 py-1 font-mono text-[9px] uppercase tracking-wider text-[#67877d]">Illustrative trend</span>
            </div>
            <div className="h-[310px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={TREND} margin={{ top: 8, right: 8, left: -22, bottom: 0 }}>
                  <defs>
                    <linearGradient id="traceGlow" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#7CF7D4" stopOpacity={0.34} />
                      <stop offset="100%" stopColor="#7CF7D4" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="rgba(183,255,229,.07)" vertical={false} />
                  <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#628378', fontFamily: 'var(--font-mono)', fontSize: 9 }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: '#628378', fontFamily: 'var(--font-mono)', fontSize: 9 }} />
                  <Tooltip contentStyle={{ background: '#0b1b17', border: '1px solid rgba(183,255,229,.15)', borderRadius: 14, color: '#effff9', fontFamily: 'var(--font-mono)', fontSize: 10 }} />
                  <Area type="monotone" dataKey="traces" stroke="#7CF7D4" strokeWidth={2} fill="url(#traceGlow)" />
                  <Area type="monotone" dataKey="latency" stroke="#9B87FF" strokeWidth={1.5} fill="transparent" strokeDasharray="4 5" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-3 flex gap-5 font-mono text-[9px] uppercase tracking-wider text-[#789b90]">
              <span className="flex items-center gap-2"><span className="h-px w-5 bg-[#7cf7d4]" /> Trace volume</span>
              <span className="flex items-center gap-2"><span className="h-px w-5 bg-[#9b87ff]" /> Latency envelope</span>
            </div>
          </div>

          <div className="glass-panel rounded-3xl p-5 md:p-7">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-mono text-[9px] uppercase tracking-[.2em] text-[#789b90]">Provider mesh</div>
                <h3 className="mt-2 text-xl font-medium text-[#effff9]">Execution surfaces</h3>
              </div>
              <DatabaseZap size={18} className="text-[#7cf7d4]" />
            </div>
            <div className="mt-7 space-y-2">
              {providerEntries.length ? providerEntries.map(([name, config]) => (
                <div key={name} className="flex items-center justify-between rounded-2xl border border-[#b7ffe5]/10 bg-[#b7ffe5]/[.025] p-4">
                  <div>
                    <div className="text-sm font-medium text-[#e9fff7]">{name}</div>
                    <div className="mt-1 font-mono text-[9px] text-[#628378]">${config.cost_per_1k ?? 0} / 1k tokens</div>
                  </div>
                  <span className={`rounded-full border px-2.5 py-1 font-mono text-[8px] uppercase tracking-wider ${config.status === 'healthy' ? 'border-[#7cf7d4]/25 bg-[#7cf7d4]/10 text-[#7cf7d4]' : 'border-rose-300/25 bg-rose-300/10 text-rose-200'}`}>
                    {config.status ?? 'unknown'}
                  </span>
                </div>
              )) : (
                <div className="rounded-2xl border border-dashed border-[#b7ffe5]/15 p-8 text-center">
                  <Radio size={20} className="mx-auto text-[#628378]" />
                  <div className="mt-3 text-sm text-[#a7c4ba]">No authenticated provider data</div>
                  <div className="mt-1 font-mono text-[9px] text-[#55766c]">The console does not substitute demo providers.</div>
                </div>
              )}
            </div>
          </div>
        </section>
      </div>
    </PageLayout>
  );
}
