'use client';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { format } from 'date-fns';

export default function LedgerPage() {
  const certs = [
    {
      id: 'cert_1a2b3c4d',
      timestamp: new Date().toISOString(),
      action: 'Rollback Query Rewriter to v1.1',
      hash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
      status: 'verified'
    },
    {
      id: 'cert_9f8e7d6c',
      timestamp: new Date(Date.now() - 86400000).toISOString(),
      action: 'Override Rate Limit (Operator)',
      hash: '59a597a7605e557b7f1981d11ff3e4b47f7d98be22fb39cb012a6136d8db76cc',
      status: 'verified'
    }
  ];

  return (
    <div className="p-8">
      <div className="flex justify-between items-start mb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Certificate Ledger</h1>
          <p className="text-zinc-400">Cryptographic audit log for recovery actions</p>
        </div>
        <Badge variant="certified">Ledger Intact</Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Tamper-Evident Logs</CardTitle>
          <CardDescription>Append-only ledger linking diagnoses to state rollbacks.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Cert ID</TableHead>
                <TableHead>Timestamp</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Cryptographic Hash</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {certs.map(cert => (
                <TableRow key={cert.id}>
                  <TableCell className="font-mono text-xs">{cert.id}</TableCell>
                  <TableCell className="text-zinc-400">{format(new Date(cert.timestamp), 'MMM d, HH:mm:ss')}</TableCell>
                  <TableCell className="font-medium">{cert.action}</TableCell>
                  <TableCell className="font-mono text-[10px] text-zinc-500 max-w-[200px] truncate" title={cert.hash}>
                    {cert.hash}
                  </TableCell>
                  <TableCell>
                    <Badge variant={cert.status === 'verified' ? 'certified' : 'destructive'}>
                      {cert.status}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
