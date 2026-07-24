'use client';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

export default function SchedulerPage() {
  const arms = [
    { id: 'arm_1', name: 'Decrease Temperature (0.1)', gain: 0.15, cost: 0.05, active: true },
    { id: 'arm_2', name: 'Switch to GPT-4', gain: 0.85, cost: 0.80, active: false },
    { id: 'arm_3', name: 'Enable Dense Retrieval', gain: 0.40, cost: 0.20, active: true },
  ];

  return (
    <div className="p-8">
      <div className="flex justify-between items-start mb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">BCRB Scheduler</h1>
          <p className="text-zinc-400">Budgeted Contextual Multi-Armed Bandit Evaluation</p>
        </div>
        <Badge variant="certified">Budget: $5.00 / $10.00</Badge>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-zinc-400">Information Gain</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-400">+1.24 nats</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-zinc-400">Confidence Interval</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">[0.85, 0.92]</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-zinc-400">Stop Reason</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-400">Target Achieved</div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Candidate Arms</CardTitle>
          <CardDescription>Estimated gain vs cost trade-offs for available interventions.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Status</TableHead>
                <TableHead>Intervention Name</TableHead>
                <TableHead>Expected Gain (nats)</TableHead>
                <TableHead>Estimated Cost</TableHead>
                <TableHead>Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {arms.map(arm => (
                <TableRow key={arm.id}>
                  <TableCell>
                    <Badge variant={arm.active ? 'measured' : 'outline'}>
                      {arm.active ? 'Selected' : 'Pruned'}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-medium">{arm.name}</TableCell>
                  <TableCell>{arm.gain.toFixed(2)}</TableCell>
                  <TableCell>${arm.cost.toFixed(2)}</TableCell>
                  <TableCell>
                    <Button variant="ghost" size="sm">Details</Button>
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
