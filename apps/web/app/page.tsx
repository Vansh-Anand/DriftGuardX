"use client";

import Link from "next/link";
import { Activity, ArrowRight, CheckCircle2, Cpu, Gauge, GitBranch, ShieldCheck } from "lucide-react";

const proofRows = [
  ["pytest tests -q", "610 passed", "2m 46s"],
  ["web e2e", "5 passed", "chromium"],
  ["live API smoke", "health / ready / trace", "loopback"],
  ["controlled replay", "7 evidence files", "4 datasets"],
];

const metricTiles = [
  { label: "Local suite", value: "610", detail: "Python tests passed", icon: CheckCircle2 },
  { label: "Trace smoke", value: "9", detail: "spans returned live", icon: GitBranch },
  { label: "Benchmarks", value: "440", detail: "query/fault pairs", icon: Gauge },
  { label: "Boundary", value: "TRL5", detail: "candidate, local relevant env", icon: ShieldCheck },
];

export default function LandingPage() {
  return (
    <main className="min-h-screen overflow-x-hidden bg-[#050706] text-[#f4fff9]">
      <section className="relative isolate min-h-[92svh] border-b border-white/10">
        <img
          src="/media/neural-network.jpg"
          alt=""
          className="absolute inset-0 -z-20 h-full w-full object-cover opacity-25"
        />
        <div className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_70%_20%,rgba(124,247,212,.22),transparent_34%),linear-gradient(120deg,rgba(5,7,6,.92),rgba(5,7,6,.72)_45%,rgba(5,7,6,.95))]" />
        <div className="absolute inset-0 -z-10 bg-[linear-gradient(rgba(255,255,255,.045)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,.045)_1px,transparent_1px)] bg-[size:64px_64px]" />

        <nav className="mx-auto flex max-w-7xl items-center justify-between px-5 py-5 md:px-8">
          <Link href="/" className="font-mono text-xs uppercase tracking-[.28em] text-[#7cf7d4]">
            DriftGuard-X
          </Link>
          <div className="hidden items-center gap-6 font-mono text-[10px] uppercase tracking-[.16em] text-[#a8c8bd] md:flex">
            <Link href="/dashboard" className="hover:text-white">Console</Link>
            <Link href="/runs" className="hover:text-white">Runs</Link>
            <Link href="/replay" className="hover:text-white">Replay</Link>
            <Link href="/security" className="hover:text-white">Security</Link>
          </div>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 border border-[#7cf7d4]/40 px-3 py-2 font-mono text-[10px] uppercase tracking-[.14em] text-[#7cf7d4] transition hover:bg-[#7cf7d4] hover:text-[#06100e]"
          >
            Open control plane <ArrowRight size={13} />
          </Link>
        </nav>

        <div className="mx-auto grid max-w-7xl gap-10 px-5 pb-16 pt-14 md:px-8 lg:grid-cols-[1.05fr_.95fr] lg:items-center lg:pt-24">
          <div>
            <div className="mb-5 inline-flex items-center gap-3 border border-white/15 bg-white/[.03] px-3 py-2 font-mono text-[10px] uppercase tracking-[.18em] text-[#f5b849]">
              <span className="h-2 w-2 bg-[#f5b849]" />
              TRL5 candidate
            </div>
            <h1 className="max-w-5xl text-5xl font-semibold leading-[.92] tracking-[-.06em] text-white md:text-7xl xl:text-8xl">
              Real-time reliability infrastructure for agentic RAG.
            </h1>
            <p className="mt-7 max-w-2xl text-base leading-7 text-[#b7d1c8] md:text-lg">
              DriftGuard-X traces failures, verifies replay admission receipts, blocks unsafe remediation,
              and keeps every result attached to its evidence class. Built as a local relevant-environment
              prototype with measured validation, not unchecked automation.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link
                href="/dashboard"
                className="inline-flex items-center justify-center gap-2 bg-[#7cf7d4] px-5 py-3 font-mono text-xs uppercase tracking-[.14em] text-[#06100e] transition hover:bg-white"
              >
                Open control plane <ArrowRight size={15} />
              </Link>
              <Link
                href="/replay"
                className="inline-flex items-center justify-center gap-2 border border-white/18 px-5 py-3 font-mono text-xs uppercase tracking-[.14em] text-white transition hover:border-[#f5b849] hover:text-[#f5b849]"
              >
                Trigger replay lab <Activity size={15} />
              </Link>
            </div>
          </div>

          <div className="grid gap-4">
            <div className="border border-white/12 bg-[#07110f]/86 p-4 shadow-2xl shadow-black/40">
              <div className="mb-4 flex items-center justify-between border-b border-white/10 pb-3">
                <div className="font-mono text-[10px] uppercase tracking-[.18em] text-[#7cf7d4]">Terminal</div>
                <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[.16em] text-[#a8c8bd]">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#7cf7d4]" /> local relevant env
                </div>
              </div>
              <pre className="overflow-hidden font-mono text-[11px] leading-6 text-[#dffdf3]">
{`$ dgx verify-local
✓ authenticated API smoke
✓ receipt mismatch refusal
✓ replay boundary enforced
✓ Playwright console checks
✓ evidence class retained

admission.store     durable
executor.dispatch   guarded
audit.chain         append-only`}
              </pre>
            </div>

            <div className="grid grid-cols-2 gap-3">
              {metricTiles.map(({ label, value, detail, icon: Icon }) => (
                <div key={label} className="border border-white/12 bg-white/[.035] p-4">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[9px] uppercase tracking-[.18em] text-[#8eb1a5]">{label}</span>
                    <Icon size={15} className="text-[#f5b849]" />
                  </div>
                  <div className="mt-5 text-4xl font-semibold tracking-[-.06em] text-white">{value}</div>
                  <div className="mt-1 font-mono text-[10px] text-[#9fb9af]">{detail}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-6 px-5 py-14 md:px-8 lg:grid-cols-[.8fr_1.2fr]">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[.22em] text-[#7cf7d4]">Validation evidence</div>
          <h2 className="mt-3 max-w-xl text-3xl font-semibold tracking-[-.04em] text-white md:text-5xl">
            The system shows its work before it claims recovery.
          </h2>
          <p className="mt-5 max-w-lg text-sm leading-6 text-[#9fb9af]">
            TRL4/TRL5 readiness here means local integration evidence: API service smoke,
            full automated test coverage, controlled replay datasets, and refusal behavior
            under stale or mismatched state. Production deployment is still a separate gate.
          </p>
        </div>
        <div className="border border-white/12 bg-[#07110f]">
          {proofRows.map(([command, result, context], index) => (
            <div key={command} className="grid grid-cols-[1fr_auto] gap-4 border-b border-white/10 p-4 last:border-b-0 md:grid-cols-[1fr_150px_110px]">
              <div className="font-mono text-[11px] text-[#dffdf3]">{command}</div>
              <div className="font-mono text-[11px] text-[#7cf7d4]">{result}</div>
              <div className="hidden font-mono text-[10px] uppercase tracking-[.12em] text-[#8eb1a5] md:block">{context}</div>
              <div className="col-span-2 h-1 bg-white/8 md:col-span-3">
                <div
                  className="h-full bg-[#7cf7d4]"
                  style={{ width: `${index === 0 ? 100 : index === 1 ? 86 : index === 2 ? 74 : 68}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="border-t border-white/10 bg-[#f1f0e8] px-5 py-14 text-[#07110f] md:px-8">
        <div className="mx-auto grid max-w-7xl gap-8 lg:grid-cols-3">
          {[
            ["State-bound admission", "Durable receipts are issued, verified, consumed, released, voided, and refused under mismatch."],
            ["Controlled replay", "SciFact, ArguAna, NFCorpus, and FiQA artifacts separate oracle priors from unbiased strategies."],
            ["Real-time console", "The UI surfaces live service status, evidence class, provider mesh, and benchmark boundaries."],
          ].map(([title, body]) => (
            <div key={title} className="border border-[#07110f]/18 bg-white p-6">
              <Cpu size={18} className="text-[#ff4b26]" />
              <h3 className="mt-5 text-xl font-semibold tracking-[-.03em]">{title}</h3>
              <p className="mt-3 text-sm leading-6 text-[#4b5a54]">{body}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
