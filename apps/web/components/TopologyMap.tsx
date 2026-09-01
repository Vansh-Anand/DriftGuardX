import React from 'react';

interface TopologyMapProps {
  failingComponent?: string | null;
}

export function TopologyMap({ failingComponent }: TopologyMapProps) {
  // Nodes in our causal graph
  const nodes = [
    { id: 'retriever', label: 'RETRIEVER', x: 100, y: 150 },
    { id: 'generator', label: 'GENERATOR', x: 300, y: 150 },
    { id: 'policy_check', label: 'POLICY_CHECK', x: 500, y: 150 },
    { id: 'orchestrator', label: 'ORCHESTRATOR', x: 300, y: 50 },
    { id: 'verifier', label: 'VERIFIER', x: 700, y: 150 },
  ];

  const edges = [
    { from: 'orchestrator', to: 'retriever' },
    { from: 'orchestrator', to: 'generator' },
    { from: 'orchestrator', to: 'policy_check' },
    { from: 'retriever', to: 'generator' },
    { from: 'generator', to: 'policy_check' },
    { from: 'policy_check', to: 'verifier' },
  ];

  return (
    <div className="relative w-full h-80 bg-[var(--background)] border border-[var(--border)] overflow-hidden">
      {/* Drafting grid background */}
      <div className="absolute inset-0 opacity-10 pointer-events-none" style={{
        backgroundImage: 'linear-gradient(var(--foreground) 1px, transparent 1px), linear-gradient(90deg, var(--foreground) 1px, transparent 1px)',
        backgroundSize: '20px 20px'
      }} />

      <svg className="w-full h-full absolute inset-0">
        {/* Draw edges */}
        {edges.map((edge, i) => {
          const fromNode = nodes.find((n) => n.id === edge.from);
          const toNode = nodes.find((n) => n.id === edge.to);
          
          if (!fromNode || !toNode) return null;

          // Simple orthogonal path routing for the blueprint feel
          const midY = fromNode.y + (toNode.y - fromNode.y) / 2;
          const path = `M ${fromNode.x + 60} ${fromNode.y} L ${fromNode.x + 60} ${midY} L ${toNode.x + 60} ${midY} L ${toNode.x + 60} ${toNode.y}`;

          return (
            <path
              key={i}
              d={path}
              fill="none"
              stroke="var(--foreground)"
              strokeWidth="1"
              strokeDasharray="4 2"
              className="opacity-40"
            />
          );
        })}

        {/* Draw nodes */}
        {nodes.map((node) => {
          const isFailing = failingComponent === node.id;
          
          return (
            <g key={node.id} transform={`translate(${node.x}, ${node.y - 20})`}>
              <rect
                x="0"
                y="0"
                width="120"
                height="40"
                fill={isFailing ? 'var(--accent)' : 'var(--background)'}
                stroke={isFailing ? 'var(--accent)' : 'var(--foreground)'}
                strokeWidth="1"
                className="transition-colors duration-500"
              />
              <text
                x="60"
                y="24"
                textAnchor="middle"
                className={`font-mono text-xs font-bold tracking-widest ${isFailing ? 'fill-background' : 'fill-foreground'}`}
              >
                {node.label}
              </text>
              
              {/* Drafting crosshairs */}
              <path d="M -5 20 L 5 20 M 0 15 L 0 25" stroke={isFailing ? 'var(--background)' : 'var(--foreground)'} strokeWidth="0.5" />
              <path d="M 115 20 L 125 20 M 120 15 L 120 25" stroke={isFailing ? 'var(--background)' : 'var(--foreground)'} strokeWidth="0.5" />
            </g>
          );
        })}
      </svg>
      
      {/* Target reticle for failing component if applicable */}
      {failingComponent && (
        <div className="absolute bottom-4 right-4 text-[var(--accent)] font-mono text-xs uppercase tracking-widest flex items-center gap-2">
          <span className="w-2 h-2 bg-[var(--accent)] block" />
          Quarantine Target Lock: {failingComponent}
        </div>
      )}
    </div>
  );
}
