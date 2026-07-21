'use client';

import { useState, useEffect } from 'react';

export default function Home() {
  const [telemetryData, setTelemetryData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // In a real app, the tenant_id would come from auth context
    const tenantId = '00000000-0000-0000-0000-000000000000'; // Default UUID for demo
    
    fetch(`http://localhost:8000/v1/telemetry/quality/${tenantId}`)
      .then(res => res.json())
      .then(data => {
        setTelemetryData(data);
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to fetch telemetry", err);
        setLoading(false);
      });
  }, []);

  return (
    <main className="flex min-h-screen flex-col items-center justify-start p-12 bg-black text-white font-mono">
      <div className="w-full max-w-5xl mb-12 flex justify-between items-center border-b border-gray-800 pb-4">
        <h1 className="text-2xl font-bold text-blue-400">DriftGuard-X Telemetry Console</h1>
        <div className="text-sm text-gray-500">Live Quality Metrics</div>
      </div>

      <div className="w-full max-w-5xl grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="glass-panel p-6 border border-gray-800 rounded-xl bg-zinc-900">
          <h3 className="text-gray-400 text-sm mb-2">Total Traces</h3>
          <p className="text-4xl font-bold">{loading ? '-' : telemetryData?.metrics?.total_traces || 0}</p>
        </div>
        
        <div className="glass-panel p-6 border border-gray-800 rounded-xl bg-zinc-900">
          <h3 className="text-gray-400 text-sm mb-2">Total Spans</h3>
          <p className="text-4xl font-bold">{loading ? '-' : telemetryData?.metrics?.total_spans || 0}</p>
        </div>

        <div className="glass-panel p-6 border border-gray-800 rounded-xl bg-zinc-900">
          <h3 className="text-gray-400 text-sm mb-2">Missing Tags (Completeness)</h3>
          <p className="text-4xl font-bold text-yellow-500">{loading ? '-' : telemetryData?.metrics?.spans_missing_tags || 0}</p>
        </div>
      </div>

      <div className="w-full max-w-5xl mt-12">
        <h2 className="text-xl font-bold mb-4">Ingestion Health</h2>
        <div className="glass-panel p-6 border border-gray-800 rounded-xl bg-zinc-900">
           <div className="flex justify-between py-2 border-b border-gray-800">
             <span className="text-gray-400">Errors Recorded</span>
             <span className="font-bold text-red-400">{loading ? '-' : telemetryData?.metrics?.total_errors || 0}</span>
           </div>
           <div className="flex justify-between py-2 border-b border-gray-800">
             <span className="text-gray-400">Duplicate Span Rate</span>
             <span className="font-bold">{loading ? '-' : telemetryData?.metrics?.duplicate_rate || 0}%</span>
           </div>
           <div className="flex justify-between py-2">
             <span className="text-gray-400">Average Ingestion Lag</span>
             <span className="font-bold">{loading ? '-' : telemetryData?.metrics?.ingestion_lag_ms || 0} ms</span>
           </div>
        </div>
      </div>
    </main>
  );
}
