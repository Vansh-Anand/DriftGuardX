'use client';

import { useState, useEffect } from 'react';
import ReactFlow, { 
  MiniMap, 
  Controls, 
  Background, 
  useNodesState, 
  useEdgesState,
  MarkerType,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { fetchGraphSnapshot } from '@/lib/api';

const nodeColor: Record<string, string> = {
  query: '#3b82f6',
  request: '#3b82f6',
  retriever: '#10b981',
  model: '#8b5cf6',
};

interface GraphNodeData {
  label: string;
}

export default function GraphExplorer({ params }: { params: { run_id: string } }) {
  const [nodes, setNodes, onNodesChange] = useNodesState<GraphNodeData>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchGraphSnapshot(params.run_id)
      .then(data => {
        setNodes(data.nodes.map((node, index) => ({
          id: node.id,
          position: { x: (index % 4) * 240, y: Math.floor(index / 4) * 140 },
          data: { label: node.label },
          style: { backgroundColor: nodeColor[node.type] ?? '#374151', color: 'white' },
        })));
        setEdges(data.edges.map(edge => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          label: edge.label || edge.type,
          markerEnd: { type: MarkerType.ArrowClosed },
        })));
        setLoading(false);
      })
      .catch((err: Error) => {
        setError(err.message);
        setLoading(false);
      });
  }, [params.run_id, setEdges, setNodes]);

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
        {loading && <div className="p-8 text-sm text-gray-400">Loading authenticated graph…</div>}
        {error && <div className="p-8 text-sm text-red-300">Graph unavailable: {error}</div>}
        {!loading && !error && nodes.length === 0 && (
          <div className="p-8 text-sm text-gray-400">This run has no graph snapshot.</div>
        )}
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
