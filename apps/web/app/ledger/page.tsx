'use client';
import { PageLayout } from '@/components/PageLayout';
import Link from 'next/link';
import { format } from 'date-fns';

const certs = [
  {
    id: 'cert_1a2b3c4d',
    timestamp: new Date().toISOString(),
    action: 'Rollback Query Rewriter to v1.1',
    hash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    domain_prefix: '0x01',
    status: 'verified',
    tenant: 'T_111',
    evidence_kind: 'synthetic_simulation',
  },
  {
    id: 'cert_9f8e7d6c',
    timestamp: new Date(Date.now() - 86400000).toISOString(),
    action: 'Override Rate Limit (Operator)',
    hash: '59a597a7605e557b7f1981d11ff3e4b47f7d98be22fb39cb012a6136d8db76cc',
    domain_prefix: '0x01',
    status: 'verified',
    tenant: 'T_222',
    evidence_kind: 'controlled_replay',
  },
  {
    id: 'cert_5c4d3e2f',
    timestamp: new Date(Date.now() - 172800000).toISOString(),
    action: 'Apply Semantic Drift Threshold Update',
    hash: 'a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3',
    domain_prefix: '0x00',
    status: 'verified',
    tenant: 'T_111',
    evidence_kind: 'production_canary',
  },
];

export default function LedgerPage() {
  const badge = (
    <span className="font-mono text-[10px] border border-[#0a0a0a] px-3 py-1.5 uppercase tracking-widest bg-[#0a0a0a] text-[#ECEAE2]">
      Ledger Intact
    </span>
  );

  return (
    <PageLayout title="Certificate Ledger" subtitle="Tamper-evident cryptographic audit log for recovery actions" badge={badge}>
      <div className="p-8">

        {/* Integrity summary */}
        <div className="grid grid-cols-3 border border-[#0a0a0a] mb-8">
          <div className="p-5">
            <div className="font-mono text-[10px] text-[#888] uppercase tracking-[0.15em] mb-2">Total Certificates</div>
            <div className="font-sans font-bold text-3xl">{certs.length}</div>
          </div>
          <div className="border-l border-[#0a0a0a] p-5">
            <div className="font-mono text-[10px] text-[#888] uppercase tracking-[0.15em] mb-2">Hash Function</div>
            <div className="font-mono text-sm font-bold">SHA-256</div>
            <div className="font-mono text-[10px] text-[#888]">Domain-separated (0x00/0x01)</div>
          </div>
          <div className="border-l border-[#0a0a0a] p-5">
            <div className="font-mono text-[10px] text-[#888] uppercase tracking-[0.15em] mb-2">Verified</div>
            <div className="font-sans font-bold text-3xl text-[#0a0a0a]">{certs.filter(c => c.status === 'verified').length}</div>
            <div className="font-mono text-[10px] text-[#888]">All entries verified</div>
          </div>
        </div>

        {/* Certificate table */}
        <div className="border border-[#0a0a0a]">
          {/* Header */}
          <div className="grid grid-cols-[120px_150px_1fr_170px_150px_70px_80px] border-b border-[#0a0a0a] bg-[#0a0a0a] text-[#ECEAE2]">
            {['Cert ID', 'Timestamp', 'Action', 'Hash (SHA-256)', 'Evidence', 'Domain', 'Status'].map(h => (
              <div key={h} className="font-mono text-[10px] tracking-[0.1em] uppercase px-4 py-3">{h}</div>
            ))}
          </div>
          {certs.map((cert, i) => (
            <div key={cert.id} className={`grid grid-cols-[120px_150px_1fr_170px_150px_70px_80px] items-start ${i > 0 ? 'border-t border-[#0a0a0a]/10' : ''} hover:bg-[#0a0a0a]/5 transition-colors`}>
              <div className="px-4 py-4 font-mono text-[10px] text-[#0a0a0a] break-all">{cert.id}</div>
              <div className="px-4 py-4 font-mono text-[10px] text-[#888]">{format(new Date(cert.timestamp), 'MMM d, HH:mm:ss')}</div>
              <div className="px-4 py-4 font-mono text-xs font-medium text-[#0a0a0a]">{cert.action}</div>
              <div className="px-4 py-4 font-mono text-[10px] text-[#888] truncate" title={cert.hash}>{cert.hash.substring(0, 24)}...</div>
              <div className="px-4 py-4 font-mono text-[10px] uppercase text-amber-700">{cert.evidence_kind.replaceAll('_', ' ')}</div>
              <div className="px-4 py-4 font-mono text-[10px] text-[#888]">{cert.domain_prefix}</div>
              <div className="px-4 py-4">
                <span className={`font-mono text-[10px] border px-2 py-0.5 uppercase tracking-wider ${cert.status === 'verified' ? 'border-[#0a0a0a] text-[#0a0a0a]' : 'border-red-500 text-red-600'}`}>
                  {cert.status}
                </span>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-6 font-mono text-[10px] text-[#888] border border-[#0a0a0a]/20 px-4 py-3">
          Merkle root computed with domain separation: LEAF_DOMAIN=0x00, INTERNAL_DOMAIN=0x01. Deterministic JSON canonicalization. Append-only log.
          Synthetic certificates attest integrity only and never authorize production execution.
        </div>
      </div>
    </PageLayout>
  );
}
