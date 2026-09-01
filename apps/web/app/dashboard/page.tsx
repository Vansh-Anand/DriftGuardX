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
    <div className="bg-[var(--background)] border border-[var(--border)] relative overflow-hidden p-5 transition-transform duration-300 hover:-translate-y-1">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[9px] uppercase tracking-[.2em] text-[var(--muted)]">{label}</span>
        <span className="grid h-8 w-8 place-items-center border border-[var(--border)] bg-transparent text-[var(--foreground)]">
          <Icon size={14} />
        </span>
      </div>
      <div className="mt-5 flex items-end gap-2">
        <span className="text-4xl font-semibold tracking-[-.05em] text-[var(--foreground)]">{value}</span>
        {signal && <span className="mb-2 h-1.5 w-1.5 rounded-full bg-[var(--accent)] animate-pulse" />}
      </div>
      <div className="mt-2 font-mono text-[10px] text-[var(--muted)]">{sub}</div>
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
    <span className={`inline-flex items-center gap-2 border px-3 py-1.5 font-mono text-[9px] uppercase tracking-[.16em] ${connected ? 'border-[var(--foreground)] bg-transparent text-[var(--foreground)]' : 'border-[var(--accent)] text-[var(--accent)]'}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${connected ? 'bg-[var(--foreground)] animate-pulse' : 'bg-[var(--accent)]'}`} />
      {connected ? 'Authenticated stream' : 'Awaiting telemetry'}
    </span>
  );

  if (loading) {
    return (
      <PageLayout title="Overview" subtitle="Evidence-aware system health and reliability signals" badge={badge}>
        <div className="grid min-h-[60vh] place-items-center"><Spinner className="h-8 w-8 text-[var(--foreground)]" /></div>
      </PageLayout>
    );
  }

  const metrics = telemetry?.metrics;
  const providerEntries = Object.entries(providers ?? {});

  return (
    <PageLayout title="Overview" subtitle="Evidence-aware system health and reliability signals" badge={badge}>
      <div className="mx-auto max-w-[1500px] space-y-6 p-4 md:p-8">
        <section className="bg-[var(--background)] border border-[var(--border)] relative overflow-hidden p-6 md:p-8 shadow-[8px_8px_0_0_var(--foreground)]">
          <div className="relative grid gap-8 xl:grid-cols-[1.35fr_.65fr] xl:items-end">
            <div>
              <div className="mb-4 inline-flex items-center gap-2 border border-[var(--border)] bg-transparent px-3 py-1 font-mono text-[9px] uppercase tracking-[.18em] text-[var(--foreground)]">
                <ShieldCheck size={12} /> Research evidence boundary active
              </div>
              <h2 className="max-w-3xl text-3xl font-semibold leading-[1.05] tracking-[-.04em] text-[var(--foreground)] md:text-5xl">
                See the failure path.<br /><span className="text-[var(--accent)]">Prove the recovery path.</span>
              </h2>
              <p className="mt-4 max-w-2xl font-mono text-[11px] leading-6 text-[var(--muted)]">
                Every diagnosis stays attached to its evidence class. Synthetic evaluations cannot silently become replay or production claims.
              </p>
            </div>
            <div className="grid grid-cols-3 gap-2 border border-[var(--border)] bg-transparent p-3 shadow-[4px_4px_0_0_var(--foreground)]">
              {['Trace', 'Replay', 'Certify'].map((step, index) => (
                <div key={step} className="relative border border-[var(--border)] bg-transparent px-3 py-4 text-center">
                  <div className="font-mono text-[9px] text-[var(--muted)]">0{index + 1}</div>
                  <div className="mt-1 text-xs font-bold uppercase tracking-widest text-[var(--foreground)]">{step}</div>
                  {index < 2 && <span className="absolute -right-2 top-1/2 z-10 text-[var(--foreground)]">→</span>}
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
          <div className="bg-[var(--background)] border border-[var(--border)] p-5 md:p-7 shadow-[4px_4px_0_0_var(--foreground)]">
            <div className="mb-8 flex items-start justify-between gap-4">
              <div>
                <div className="font-mono text-[9px] uppercase tracking-[.2em] text-[var(--muted)]">Signal topology</div>
                <h3 className="mt-2 text-xl font-medium text-[var(--foreground)]">Trace volume and latency envelope</h3>
              </div>
              <span className="border border-[var(--border)] px-3 py-1 font-mono text-[9px] uppercase tracking-wider text-[var(--muted)]">Illustrative trend</span>
            </div>
            <div className="h-[310px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={TREND} margin={{ top: 8, right: 8, left: -22, bottom: 0 }}>
                  <defs>
                    <linearGradient id="traceGlow" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#090B0A" stopOpacity={0.15} />
                      <stop offset="100%" stopColor="#090B0A" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: 'var(--muted)', fontFamily: 'var(--font-mono)', fontSize: 9 }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: 'var(--muted)', fontFamily: 'var(--font-mono)', fontSize: 9 }} />
                  <Tooltip contentStyle={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)', fontFamily: 'var(--font-mono)', fontSize: 10 }} />
                  <Area type="monotone" dataKey="traces" stroke="var(--foreground)" strokeWidth={2} fill="url(#traceGlow)" />
                  <Area type="monotone" dataKey="latency" stroke="var(--muted)" strokeWidth={1.5} fill="transparent" strokeDasharray="4 5" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-3 flex gap-5 font-mono text-[9px] uppercase tracking-wider text-[var(--muted)]">
              <span className="flex items-center gap-2"><span className="h-px w-5 bg-[var(--foreground)]" /> Trace volume</span>
              <span className="flex items-center gap-2"><span className="h-px w-5 bg-[var(--muted)]" /> Latency envelope</span>
            </div>
          </div>

          <div className="bg-[var(--background)] border border-[var(--border)] p-5 md:p-7 shadow-[4px_4px_0_0_var(--foreground)]">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-mono text-[9px] uppercase tracking-[.2em] text-[var(--muted)]">Provider mesh</div>
                <h3 className="mt-2 text-xl font-medium text-[var(--foreground)]">Execution surfaces</h3>
              </div>
              <DatabaseZap size={18} className="text-[var(--foreground)]" />
            </div>
            <div className="mt-7 space-y-2">
              {providerEntries.length ? providerEntries.map(([name, config]) => (
                <div key={name} className="flex items-center justify-between border border-[var(--border)] bg-transparent p-4">
                  <div>
                    <div className="text-sm font-bold uppercase tracking-widest text-[var(--foreground)]">{name}</div>
                    <div className="mt-1 font-mono text-[9px] text-[var(--muted)]">${config.cost_per_1k ?? 0} / 1k tokens</div>
                  </div>
                  <span className={`border px-2.5 py-1 font-mono text-[8px] uppercase tracking-wider ${config.status === 'healthy' ? 'border-[var(--foreground)] text-[var(--foreground)]' : 'border-[var(--accent)] text-[var(--accent)]'}`}>
                    {config.status ?? 'unknown'}
                  </span>
                </div>
              )) : (
                <div className="border border-dashed border-[var(--border)] p-8 text-center">
                  <Radio size={20} className="mx-auto text-[var(--muted)]" />
                  <div className="mt-3 text-sm text-[var(--foreground)]">No authenticated provider data</div>
                  <div className="mt-1 font-mono text-[9px] text-[var(--muted)]">The console does not substitute demo providers.</div>
                </div>
              )}
            </div>
          </div>
        </section>
      </div>
    </PageLayout>
  );
}
