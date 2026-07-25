"use client";

import React, { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export default function ExperimentsPage() {
  const [experiments, setExperiments] = useState<any[]>([]);

  useEffect(() => {
    // In a real app, this would fetch from a Next.js API route that reads from the MLflow API
    // For now, we mock the UI state to demonstrate the registry
    setExperiments([
      { id: "smoke-1", name: "smoke", regime: "retrieval-only", status: "COMPLETED", success_rate: 0.8 },
      { id: "smoke-2", name: "tool-smoke", regime: "tool-use", status: "FAILED", success_rate: 0.0 }
    ]);
  }, []);

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-bold tracking-tight text-white mb-2">Experiment Registry</h1>
          <p className="text-gray-400">View and manage frozen benchmark runs across all regimes.</p>
        </div>
        <Button onClick={() => alert('Trigger run using the CLI for now.')} variant="default">
          Run Experiment
        </Button>
      </div>

      <Card className="border-gray-800 bg-gray-950">
        <CardHeader>
          <CardTitle className="text-xl text-white">Recent Runs</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border border-gray-800">
            <Table>
              <TableHeader>
                <TableRow className="border-gray-800 hover:bg-gray-900/50">
                  <TableHead className="text-gray-400">Experiment Name</TableHead>
                  <TableHead className="text-gray-400">Regime</TableHead>
                  <TableHead className="text-gray-400">Status</TableHead>
                  <TableHead className="text-gray-400">Success Rate</TableHead>
                  <TableHead className="text-gray-400">Artifacts</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {experiments.map((exp) => (
                  <TableRow key={exp.id} className="border-gray-800 hover:bg-gray-900/50">
                    <TableCell className="font-medium text-white">{exp.name}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-blue-400 border-blue-400/20 bg-blue-400/10">
                        {exp.regime}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={exp.status === "COMPLETED" ? "default" : "destructive"}>
                        {exp.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-gray-300">
                      {(exp.success_rate * 100).toFixed(1)}%
                    </TableCell>
                    <TableCell>
                      <Button variant="link" className="text-purple-400 p-0 h-auto">View MLflow</Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
      
      <div className="grid grid-cols-2 gap-8 mt-8">
        <Card className="border-gray-800 bg-gray-950">
           <CardHeader>
              <CardTitle className="text-xl text-white">Drift Performance</CardTitle>
           </CardHeader>
           <CardContent>
              <div className="bg-gray-900 h-64 rounded-md flex items-center justify-center border border-gray-800">
                 <p className="text-gray-500">Run CLI plot command to generate plots in /reports.</p>
              </div>
           </CardContent>
        </Card>
        <Card className="border-gray-800 bg-gray-950">
           <CardHeader>
              <CardTitle className="text-xl text-white">BCRB Efficiency Frontier</CardTitle>
           </CardHeader>
           <CardContent>
              <div className="bg-gray-900 h-64 rounded-md flex items-center justify-center border border-gray-800">
                 <p className="text-gray-500">Run CLI plot command to generate plots in /reports.</p>
              </div>
           </CardContent>
        </Card>
      </div>
    </div>
  );
}
