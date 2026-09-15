'use client';

import { useEffect, useState } from 'react';
import {
  Activity,
  CheckCircle2,
  DatabaseZap,
  FlaskConical,
  Layers3,
  Radio,
  Server,
  ShieldCheck,
  TriangleAlert,
  type LucideIcon,
} from 'lucide-react';
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
    spans_with_provenance?: number;
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

const TRL_CHECKS = [
  {
    label: 'Full local suite',
    value: '610 passed',
    detail: '22 skipped, 7 known warnings',
    icon: CheckCircle2,
  },
  {
    label: 'Live API smoke',
    value: 'healthy',
    detail: 'auth refusal, providers, run, trace',
    icon: Server,
  },
  {
    label: 'Controlled replay evidence',
    value: '4 datasets',
    detail: '440 query/fault pairs verified',
    icon: FlaskConical,
  },
];

const BENCHMARK_ROWS = [
  { dataset: 'SciFact', pairs: 147, mean: '2.68', note: 'Two seeds; controlled BM25 replay' },
  { dataset: 'ArguAna', pairs: 138, mean: '2.30', note: 'Two seeds; argumentative retrieval' },
  { dataset: 'NFCorpus', pairs: 122, mean: '2.37', note: 'Two seeds; biomedical corpus' },
  { dataset: 'FiQA', pairs: 33, mean: '2.39', note: 'One seed; financial QA' },
];

function StatCard({ icon: Icon, label, value, sub, signal = false }: {
  icon: LucideIcon;
  label: string;
  value: string | number;
  sub: string;
  signal?: boolean;
}) {
  return (
    <div className="relative overflow-hidden border border-[#b7ffe5]/12 bg-[#07110f] p-5 transition-transform duration-300 hover:-translate-y-1">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[9px] uppercase tracking-[.2em] text-[#8eb1a5]">{label}</span>
        <span className="grid h-8 w-8 place-items-center border border-[#b7ffe5]/12 bg-white/[.025] text-[#7cf7d4]">
          <Icon size={14} />
        </span>
      </div>
      <div className="mt-5 flex items-end gap-2">
        <span className="text-4xl font-semibold tracking-[-.05em] text-white">{value}</span>
        {signal && <span className="mb-2 h-1.5 w-1.5 rounded-full bg-[#7cf7d4] animate-pulse" />}
      </div>
      <div className="mt-2 font-mono text-[10px] text-[#8eb1a5]">{sub}</div>
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
    <span className={`inline-flex items-center gap-2 border px-3 py-1.5 font-mono text-[9px] uppercase tracking-[.16em] ${connected ? 'border-[#7cf7d4]/35 bg-[#7cf7d4]/8 text-[#7cf7d4]' : 'border-[#ff4b26] text-[#ff4b26]'}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${connected ? 'bg-[#7cf7d4] animate-pulse' : 'bg-[#ff4b26]'}`} />
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
      <div className="mx-auto max-w-[1500px] space-y-6 bg-[#050706] p-4 md:p-8">
        <section className="relative overflow-hidden border border-[#b7ffe5]/12 bg-[#07110f] p-6 md:p-8">
          <div className="absolute inset-0 opacity-30 [background-image:linear-gradient(rgba(124,247,212,.08)_1px,transparent_1px),linear-gradient(90deg,rgba(124,247,212,.08)_1px,transparent_1px)] [background-size:44px_44px]" />
          <div className="relative grid gap-8 xl:grid-cols-[1.35fr_.65fr] xl:items-end">
            <div>
              <div className="mb-4 inline-flex items-center gap-2 border border-[#7cf7d4]/28 bg-[#7cf7d4]/8 px-3 py-1 font-mono text-[9px] uppercase tracking-[.18em] text-[#7cf7d4]">
                <ShieldCheck size={12} /> TRL validation boundary active
              </div>
              <h2 className="max-w-3xl text-3xl font-semibold leading-[1.05] tracking-[-.04em] text-white md:text-5xl">
                Real-time recovery evidence.<br /><span className="text-[#7cf7d4]">Bounded before dispatch.</span>
              </h2>
              <p className="mt-4 max-w-2xl font-mono text-[11px] leading-6 text-[#9fb9af]">
                Every diagnosis stays attached to its evidence class. Synthetic evaluations cannot silently become replay, production, or patent-readiness claims.
              </p>
            </div>
            <div className="grid grid-cols-3 gap-2 border border-[#b7ffe5]/12 bg-black/20 p-3">
              {['Trace', 'Replay', 'Certify'].map((step, index) => (
                <div key={step} className="relative border border-[#b7ffe5]/12 bg-white/[.03] px-3 py-4 text-center">
                  <div className="font-mono text-[9px] text-[#8eb1a5]">0{index + 1}</div>
                  <div className="mt-1 text-xs font-bold uppercase tracking-widest text-white">{step}</div>
                  {index < 2 && <span className="absolute -right-2 top-1/2 z-10 text-[#7cf7d4]">→</span>}
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="grid gap-3 lg:grid-cols-3">
          {TRL_CHECKS.map(({ label, value, detail, icon: Icon }) => (
            <div key={label} className="border border-[#b7ffe5]/12 bg-[#07110f] p-5">
              <div className="flex items-center justify-between">
                <div className="font-mono text-[9px] uppercase tracking-[.2em] text-[#8eb1a5]">TRL validation</div>
                <Icon size={16} className="text-[#f5b849]" />
              </div>
              <div className="mt-5 text-3xl font-semibold tracking-[-.05em] text-white">{value}</div>
              <div className="mt-2 text-sm font-medium text-[#dffdf3]">{label}</div>
              <div className="mt-1 font-mono text-[10px] text-[#8eb1a5]">{detail}</div>
            </div>
          ))}
        </section>

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard icon={Activity} label="Total traces" value={metrics?.total_traces ?? '—'} sub={connected ? 'Tenant-scoped executions' : 'Sign in to connect'} signal={connected} />
          <StatCard icon={Layers3} label="Total spans" value={metrics?.total_spans ?? '—'} sub="Versioned causal observations" />
          <StatCard icon={ShieldCheck} label="Provenance tagged" value={metrics?.spans_with_provenance ?? '—'} sub="Fully verified origin" />
          <StatCard icon={Radio} label="Ingestion lag" value={metrics ? `${metrics.ingestion_lag_ms ?? 0}ms` : '—'} sub="Authenticated stream latency" />
        </section>

        <section className="grid gap-6 xl:grid-cols-[1.45fr_.55fr]">
          <div className="border border-[#b7ffe5]/12 bg-[#07110f] p-5 md:p-7">
            <div className="mb-8 flex items-start justify-between gap-4">
              <div>
                <div className="font-mono text-[9px] uppercase tracking-[.2em] text-[#8eb1a5]">Signal topology</div>
                <h3 className="mt-2 text-xl font-medium text-white">Trace volume and latency envelope</h3>
              </div>
              <span className="border border-[#b7ffe5]/12 px-3 py-1 font-mono text-[9px] uppercase tracking-wider text-[#8eb1a5]">Illustrative trend</span>
            </div>
            <div className="h-[310px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={TREND} margin={{ top: 8, right: 8, left: -22, bottom: 0 }}>
                  <defs>
                    <linearGradient id="traceGlow" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#7cf7d4" stopOpacity={0.28} />
                      <stop offset="100%" stopColor="#7cf7d4" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="rgba(183,255,229,.1)" vertical={false} />
                  <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#8eb1a5', fontFamily: 'var(--font-mono)', fontSize: 9 }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: '#8eb1a5', fontFamily: 'var(--font-mono)', fontSize: 9 }} />
                  <Tooltip contentStyle={{ background: '#07110f', border: '1px solid rgba(183,255,229,.14)', color: '#f4fff9', fontFamily: 'var(--font-mono)', fontSize: 10 }} />
                  <Area type="monotone" dataKey="traces" stroke="#7cf7d4" strokeWidth={2} fill="url(#traceGlow)" />
                  <Area type="monotone" dataKey="latency" stroke="#f5b849" strokeWidth={1.5} fill="transparent" strokeDasharray="4 5" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-3 flex gap-5 font-mono text-[9px] uppercase tracking-wider text-[#8eb1a5]">
              <span className="flex items-center gap-2"><span className="h-px w-5 bg-[#7cf7d4]" /> Trace volume</span>
              <span className="flex items-center gap-2"><span className="h-px w-5 bg-[#f5b849]" /> Latency envelope</span>
            </div>
          </div>

          <div className="border border-[#b7ffe5]/12 bg-[#07110f] p-5 md:p-7">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-mono text-[9px] uppercase tracking-[.2em] text-[#8eb1a5]">Provider mesh</div>
                <h3 className="mt-2 text-xl font-medium text-white">Execution surfaces</h3>
              </div>
              <DatabaseZap size={18} className="text-[#7cf7d4]" />
            </div>
            <div className="mt-7 space-y-2">
              {providerEntries.length ? providerEntries.map(([name, config]) => (
                <div key={name} className="flex items-center justify-between border border-[#b7ffe5]/12 bg-white/[.025] p-4">
                  <div>
                    <div className="text-sm font-bold uppercase tracking-widest text-white">{name}</div>
                    <div className="mt-1 font-mono text-[9px] text-[#8eb1a5]">${config.cost_per_1k ?? 0} / 1k tokens</div>
                  </div>
                  <span className={`border px-2.5 py-1 font-mono text-[8px] uppercase tracking-wider ${config.status === 'healthy' ? 'border-[#7cf7d4]/30 text-[#7cf7d4]' : 'border-[#ff4b26] text-[#ff4b26]'}`}>
                    {config.status ?? 'unknown'}
                  </span>
                </div>
              )) : (
                <div className="border border-dashed border-[#b7ffe5]/12 p-8 text-center">
                  <Radio size={20} className="mx-auto text-[#8eb1a5]" />
                  <div className="mt-3 text-sm text-white">No authenticated provider data</div>
                  <div className="mt-1 font-mono text-[9px] text-[#8eb1a5]">The console does not substitute demo providers.</div>
                </div>
              )}
            </div>
          </div>
        </section>

        <section className="border border-[#b7ffe5]/12 bg-[#07110f] p-5 md:p-7">
          <div className="flex flex-col justify-between gap-3 border-b border-[#b7ffe5]/10 pb-5 md:flex-row md:items-end">
            <div>
              <div className="font-mono text-[9px] uppercase tracking-[.2em] text-[#8eb1a5]">Benchmark boundary</div>
              <h3 className="mt-2 text-xl font-medium text-white">Controlled replay evidence</h3>
            </div>
            <div className="font-mono text-[10px] uppercase tracking-[.14em] text-[#f5b849]">
              TRL4/TRL5 evidence, not production proof
            </div>
          </div>
          <div className="mt-5 grid gap-2">
            {BENCHMARK_ROWS.map((row) => (
              <div key={row.dataset} className="grid gap-3 border border-[#b7ffe5]/10 bg-white/[.025] p-4 md:grid-cols-[120px_110px_110px_1fr] md:items-center">
                <div className="font-semibold text-white">{row.dataset}</div>
                <div className="font-mono text-[10px] uppercase tracking-[.14em] text-[#8eb1a5]">{row.pairs} pairs</div>
                <div className="font-mono text-[10px] uppercase tracking-[.14em] text-[#7cf7d4]">mean {row.mean}</div>
                <div className="text-sm text-[#9fb9af]">{row.note}</div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </PageLayout>
  );
}
