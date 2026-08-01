"use client";

import React, { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { AnimatedSection } from "@/components/AnimatedSection";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import { Spinner } from "@/components/ui/spinner";
import { useAuth } from "@/lib/auth-context";

export default function ExperimentsPage() {
  const { user } = useAuth();
  const { toast } = useToast();
  const [experiments, setExperiments] = useState<any[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [isRunning, setIsRunning] = useState(false);

  useEffect(() => {
    setExperiments([
      { id: "smoke-1", name: "smoke", regime: "retrieval-only", status: "COMPLETED", success_rate: 0.8 },
      { id: "smoke-2", name: "tool-smoke", regime: "tool-use", status: "FAILED", success_rate: 0.0 }
    ]);
  }, []);

  const handleRunExperiment = () => {
    if (!user) {
      toast({ title: 'Authentication Required', description: 'Please log in to run experiments.', variant: 'destructive' });
      return;
    }
    setCreateOpen(true);
  };

  const confirmRun = async () => {
    setIsRunning(true);
    // Simulate network delay for experiment kickoff
    await new Promise((res) => setTimeout(res, 1200));
    
    const newExp = {
      id: `exp-${Math.floor(Math.random()*1000)}`,
      name: "custom-eval-run",
      regime: "agentic-planning",
      status: "RUNNING",
      success_rate: 0.0,
    };
    
    setExperiments(prev => [newExp, ...prev]);
    setIsRunning(false);
    setCreateOpen(false);
    
    toast({
      title: 'Experiment Started',
      description: 'The counterfactual evaluation has been queued.',
      variant: 'success'
    });
    
    // Simulate progress
    setTimeout(() => {
      setExperiments(prev => prev.map(e => e.id === newExp.id ? { ...e, status: 'COMPLETED', success_rate: 0.92 } : e));
      toast({
         title: 'Experiment Completed',
         description: 'custom-eval-run finished successfully.',
      });
    }, 5000);
  };

  return (
    <>
      <AnimatedSection className="p-8 space-y-8 max-w-7xl mx-auto min-h-screen">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-4xl font-bold tracking-tight text-white mb-2">Experiment Registry</h1>
            <p className="text-gray-400">View and manage frozen benchmark runs across all regimes.</p>
          </div>
          <Button onClick={handleRunExperiment} variant="default" className="bg-white text-black hover:bg-zinc-200">
            Run Experiment
          </Button>
        </div>

        <Card className="border-zinc-800 bg-zinc-950">
          <CardHeader>
            <CardTitle className="text-xl text-white">Recent Runs</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border border-zinc-800">
              <Table>
                <TableHeader>
                  <TableRow className="border-zinc-800 hover:bg-white/5">
                    <TableHead className="text-gray-400">Experiment Name</TableHead>
                    <TableHead className="text-gray-400">Regime</TableHead>
                    <TableHead className="text-gray-400">Status</TableHead>
                    <TableHead className="text-gray-400">Success Rate</TableHead>
                    <TableHead className="text-gray-400">Artifacts</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {experiments.map((exp) => (
                    <TableRow key={exp.id} className="border-zinc-800 hover:bg-white/5">
                      <TableCell className="font-medium text-white">
                        {exp.name}
                        {exp.status === 'RUNNING' && <Spinner className="w-3 h-3 ml-2 inline" />}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-blue-400 border-blue-400/20 bg-blue-400/10">
                          {exp.regime}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge 
                          className={exp.status === 'RUNNING' ? 'bg-amber-500/20 text-amber-500' : ''}
                          variant={exp.status === "COMPLETED" ? "default" : exp.status === 'FAILED' ? "destructive" : "outline"}
                        >
                          {exp.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-gray-300">
                        {exp.status === 'RUNNING' ? '--' : `${(exp.success_rate * 100).toFixed(1)}%`}
                      </TableCell>
                      <TableCell>
                        <Button variant="link" className="text-purple-400 p-0 h-auto">View Details</Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      </AnimatedSection>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-md bg-[#1a1a1a] border-[#333] text-white">
          <DialogHeader>
            <DialogTitle>Run New Experiment</DialogTitle>
            <DialogDescription className="text-zinc-400">
              Trigger a new Budget-Constrained Counterfactual Replay evaluation.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4 space-y-4 text-sm">
             <div>
                <span className="text-zinc-500 block mb-1">Target Regime</span>
                <div className="p-2 border border-zinc-800 rounded bg-black/50">agentic-planning</div>
             </div>
             <div>
                <span className="text-zinc-500 block mb-1">Evaluation Budget</span>
                <div className="p-2 border border-zinc-800 rounded bg-black/50">500 traces (Estimated Cost: $2.40)</div>
             </div>
          </div>
          <DialogFooter>
             <Button variant="outline" onClick={() => setCreateOpen(false)} className="text-black">Cancel</Button>
             <Button onClick={confirmRun} disabled={isRunning} className="bg-blue-600 text-white hover:bg-blue-700">
                {isRunning ? <Spinner className="w-4 h-4 mr-2" /> : null}
                Start Evaluation
             </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
