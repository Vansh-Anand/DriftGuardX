'use client';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export default function RationalePage() {
  return (
    <div className="p-8">
      <div className="flex justify-between items-start mb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Diagnosis Rationale</h1>
          <p className="text-zinc-400">Natural language reasoning for recovery</p>
        </div>
        <Badge variant="certified">Rationale Certified</Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>EXECUTIVE_SUMMARY Template</CardTitle>
          <CardDescription>Deterministic fallback rendering</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="p-4 bg-zinc-900 border border-zinc-800 rounded-lg text-sm text-zinc-300 leading-relaxed font-mono">
            <p><strong>[SYSTEM STABILITY ALERT]</strong></p>
            <p className="mt-2">DriftGuard-X detected a reliability drop in the RAG Pipeline.</p>
            <p className="mt-2">- <strong>Component:</strong> Embeddings Model</p>
            <p>- <strong>Drop:</strong> 0.41 (Critical)</p>
            <p className="mt-4"><strong>Recommended Action:</strong> Rollback Embeddings Model to v2.0</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
