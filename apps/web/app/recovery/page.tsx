"use client"
import React, { useState, useEffect } from "react";
import { TopologyMap } from "../../components/TopologyMap";
import { RecoveryCertificate } from "../../components/RecoveryCertificate";

interface CertificateData {
  id: string;
  run_id: string;
  replay_episode_id: string;
  certificate_hash: string;
  issued_by: string;
  payload_summary: string;
  is_valid: boolean;
  evidence_kind: string;
}

export default function RecoveryConsole() {
  const [certificates, setCertificates] = useState<CertificateData[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCert, setSelectedCert] = useState<CertificateData | null>(null);

  // Parse root cause component from payload_summary (e.g., "Root cause isolated to retriever.")
  const failingComponent = selectedCert?.payload_summary.match(/Root cause isolated to ([a-zA-Z_]+)\./)?.[1] || null;

  useEffect(() => {
    fetchCertificates();
  }, []);

  const fetchCertificates = async () => {
    try {
      setLoading(true);
      const res = await fetch('http://localhost:8000/v1/recovery');
      if (res.ok) {
        const data = await res.json();
        setCertificates(data);
        if (data.length > 0) setSelectedCert(data[data.length - 1]);
      }
    } catch (err) {
      console.error("Failed to fetch recovery certificates:", err);
    } finally {
      setLoading(false);
    }
  };

  const triggerFault = async () => {
    try {
      const res = await fetch('http://localhost:8000/v1/recovery/trigger', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ failure_symptom: 'Test failure triggered via UI' })
      });
      if (res.ok) {
        fetchCertificates();
      }
    } catch (err) {
      console.error("Failed to trigger fault:", err);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--background)] text-[var(--foreground)] font-sans">
      <header className="border-b border-[var(--border)] px-8 py-6 flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold uppercase tracking-tighter mb-2">Recovery Console</h1>
          <p className="text-[var(--muted)] text-sm font-mono uppercase tracking-widest">
            Diagnostic Aggregation & Fault Isolation
          </p>
        </div>
        <div>
          <button 
            onClick={triggerFault}
            className="px-6 py-2 border border-[var(--accent)] text-[var(--accent)] font-mono text-xs uppercase tracking-widest hover:bg-[var(--accent)] hover:text-[var(--background)] transition-colors"
          >
            [ Initiate Synthetic Fault ]
          </button>
        </div>
      </header>

      <main className="max-w-screen-2xl mx-auto px-8 py-12 grid grid-cols-12 gap-12">
        {/* Left Column: List of Certificates */}
        <div className="col-span-4 flex flex-col gap-4 border-r border-[var(--border)] pr-12">
          <h2 className="text-sm font-bold font-mono uppercase tracking-widest border-b border-[var(--foreground)] pb-2 mb-4">
            Recovery History
          </h2>
          
          {loading ? (
            <div className="text-[var(--muted)] font-mono text-sm animate-pulse">Scanning ledgers...</div>
          ) : certificates.length === 0 ? (
            <div className="text-[var(--muted)] font-mono text-sm">No active interventions.</div>
          ) : (
            certificates.map((cert) => (
              <button
                key={cert.id}
                onClick={() => setSelectedCert(cert)}
                className={`text-left p-4 border font-mono text-xs transition-colors ${
                  selectedCert?.id === cert.id 
                    ? 'border-[var(--foreground)] bg-[var(--foreground)] text-[var(--background)]' 
                    : 'border-[var(--border)] bg-transparent text-[var(--foreground)] hover:bg-[var(--foreground)] hover:bg-opacity-10'
                }`}
              >
                <div className="truncate font-bold mb-1">{cert.id}</div>
                <div className="truncate opacity-70">TARGET: {cert.run_id}</div>
              </button>
            ))
          )}
        </div>

        {/* Right Column: Visualization */}
        <div className="col-span-8 space-y-12">
          <section>
             <h2 className="text-sm font-bold font-mono uppercase tracking-widest mb-6">
              Agent Topology Matrix
            </h2>
            <div className="">
              <TopologyMap failingComponent={failingComponent} />
            </div>
          </section>

          <section>
            <RecoveryCertificate certificate={selectedCert} />
          </section>
        </div>
      </main>
    </div>
  );
}
