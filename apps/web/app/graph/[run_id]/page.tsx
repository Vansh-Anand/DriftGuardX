'use client';

import { useState, useEffect, useCallback } from 'react';
import ReactFlow, { 
  MiniMap, 
  Controls, 
  Background, 
  useNodesState, 
  useEdgesState,
  MarkerType
} from 'reactflow';
import 'reactflow/dist/style.css';

// Placeholder for full layout algorithm (e.g. dagre)
const initialNodes = [
  { id: '1', position: { x: 0, y: 0 }, data: { label: 'Query (v1.2)' }, style: { backgroundColor: '#3b82f6', color: 'white' } },
  { id: '2', position: { x: -100, y: 100 }, data: { label: 'Retriever (v2.0)' }, style: { backgroundColor: '#10b981', color: 'white' } },
  { id: '3', position: { x: 100, y: 100 }, data: { label: 'Model (gpt-4)' }, style: { backgroundColor: '#8b5cf6', color: 'white' } },
];

const initialEdges = [
  { id: 'e1-2', source: '1', target: '2', label: 'control_flow', markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e2-3', source: '2', target: '3', label: 'data_dependency', markerEnd: { type: MarkerType.ArrowClosed } },
];

export default function GraphExplorer({ params }: { params: { run_id: string } }) {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // In a real app, tenantId is from context
    const tenantId = '00000000-0000-0000-0000-000000000000';
    
    // Simulate fetch from API
    fetch(`http://localhost:8000/v1/graph/snapshot/${tenantId}/${params.run_id}`)
      .then(res => {
        if (!res.ok) throw new Error('Graph not found or API unavailable');
        return res.json();
      })
      .then(data => {
        // Map data to React Flow nodes/edges here...
        setLoading(false);
      })
      .catch(err => {
        console.warn("Using placeholder graph data due to:", err.message);
        setLoading(false);
      });
  }, [params.run_id]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-start bg-zinc-950 text-white font-mono">
      <div className="w-full border-b border-gray-800 p-4 bg-zinc-900 flex justify-between items-center z-10">
        <div>
          <h1 className="text-xl font-bold text-blue-400">Causal Reliability Graph</h1>
          <p className="text-xs text-gray-400">Run ID: {params.run_id}</p>
        </div>
        <div className="flex gap-4">
          <div className="flex items-center gap-2"><div className="w-3 h-3 bg-blue-500 rounded-full"></div><span className="text-sm">Query</span></div>
          <div className="flex items-center gap-2"><div className="w-3 h-3 bg-green-500 rounded-full"></div><span className="text-sm">Retriever</span></div>
          <div className="flex items-center gap-2"><div className="w-3 h-3 bg-purple-500 rounded-full"></div><span className="text-sm">Model</span></div>
        </div>
      </div>

      <div className="w-full flex-grow relative" style={{ height: 'calc(100vh - 73px)' }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          fitView
          className="bg-zinc-950"
        >
          <Controls />
          <MiniMap nodeStrokeColor="#fff" nodeColor="#1f2937" maskColor="rgba(0,0,0,0.8)" />
          <Background color="#333" gap={16} />
        </ReactFlow>
      </div>
    </main>
  );
}
