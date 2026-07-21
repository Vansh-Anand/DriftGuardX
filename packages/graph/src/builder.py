"""
DriftGuard-X v2 — Causal Graph Builder
PRIVATE — All Rights Reserved.
"""
import json
from collections import defaultdict
from typing import Dict, List, Optional, Set
from uuid import UUID, uuid4

from packages.contracts.src.graph import CausalGraph, EdgeType, GraphEdge, GraphNode, NodeType
from packages.contracts.src.models import SpanRecord, TraceArtifact
from packages.contracts.src.registry import VersionRegistry

BUILDER_VERSION = "v1.0"


class GraphBuilder:
    """
    Constructs a deterministic causal reliability graph from a normalized trace.
    """
    
    def __init__(self, version_registry: VersionRegistry):
        self.registry = version_registry

    async def build(self, trace: TraceArtifact) -> CausalGraph:
        """
        Map a trace to a Causal Graph.
        Every span becomes an execution event node, and connects to version nodes.
        """
        nodes: Dict[str, GraphNode] = {}
        edges: List[GraphEdge] = []
        
        # We will parse the trace spans and construct the DAG
        spans: List[SpanRecord] = json.loads(trace.spans_json)
        
        # 1. First Pass: Create nodes for all spans (Execution Event Nodes)
        for span in spans:
            node_type = self._map_component_to_node_type(span.get("component_type"))
            
            node_id = f"event:{span['span_id']}"
            version_id = span.get("version_id")
            
            # Fetch version features if available
            features = {}
            if version_id:
                version_record = await self.registry.get_version(trace.tenant_id, UUID(version_id))
                if version_record:
                    features["state"] = version_record.state.value
                    
            if span.get("latency_ms"):
                features["latency_ms"] = span["latency_ms"]

            node = GraphNode(
                id=node_id,
                type=node_type,
                label=span.get("name", "unnamed_span"),
                is_versioned=bool(version_id),
                version_id=UUID(version_id) if version_id else None,
                span_id=span["span_id"],
                features=features
            )
            nodes[node_id] = node

            # 2. Add structural nodes if this component is versioned (Immutable Component Nodes)
            if version_id:
                comp_node_id = f"version:{version_id}"
                if comp_node_id not in nodes:
                    comp_node = GraphNode(
                        id=comp_node_id,
                        type=node_type,
                        label=f"{span.get('name')} (v)",
                        is_versioned=True,
                        version_id=UUID(version_id),
                        span_id=None,
                        features=features
                    )
                    nodes[comp_node_id] = comp_node
                
                # Connect execution event -> version node
                edges.append(GraphEdge(
                    id=f"{node_id}->{comp_node_id}",
                    source=node_id,
                    target=comp_node_id,
                    type=EdgeType.VERSION_LINEAGE,
                    label="instance_of"
                ))

        # 3. Second Pass: Create temporal/causal edges
        span_by_id = {s["span_id"]: s for s in spans}
        for span in spans:
            node_id = f"event:{span['span_id']}"
            parent_id = span.get("parent_id")
            if parent_id and parent_id in span_by_id:
                parent_node_id = f"event:{parent_id}"
                # Control flow edge from parent to child
                edges.append(GraphEdge(
                    id=f"{parent_node_id}->{node_id}",
                    source=parent_node_id,
                    target=node_id,
                    type=EdgeType.CONTROL_FLOW,
                    label="calls"
                ))
            
            # If there's an evidence citation or memory influence in attributes, extract it
            attrs = span.get("attributes", {})
            if "dgx.memory.referenced" in attrs:
                mem_id = attrs["dgx.memory.referenced"]
                edges.append(GraphEdge(
                    id=f"memory:{mem_id}->{node_id}",
                    source=f"memory:{mem_id}",
                    target=node_id,
                    type=EdgeType.MEMORY_INFLUENCE,
                    label="recalls"
                ))
                # Add memory node if missing
                if f"memory:{mem_id}" not in nodes:
                    nodes[f"memory:{mem_id}"] = GraphNode(
                        id=f"memory:{mem_id}",
                        type=NodeType.MEMORY,
                        label="Memory Store",
                    )
        
        # Build the final graph object
        graph = CausalGraph(
            tenant_id=trace.tenant_id,
            run_id=trace.run_id,
            nodes=list(nodes.values()),
            edges=edges,
            builder_version=BUILDER_VERSION,
            trace_digest=trace.trace_digest or "unknown"
        )
        return graph

    def _map_component_to_node_type(self, component_type: Optional[str]) -> NodeType:
        if not component_type:
            return NodeType.OPERATIONAL_RESOURCE
            
        mapping = {
            "retriever": NodeType.RETRIEVER,
            "generator": NodeType.MODEL,
            "prompt": NodeType.PROMPT,
            "tool_call": NodeType.TOOL,
            "guardrail": NodeType.GUARDRAIL,
            "policy": NodeType.POLICY
        }
        return mapping.get(component_type.lower(), NodeType.OPERATIONAL_RESOURCE)
