"""
DriftGuard-X v2 — Causal Graph Builder
PRIVATE — All Rights Reserved.
"""

from uuid import UUID

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
        nodes: dict[str, GraphNode] = {}
        edges: list[GraphEdge] = []

        # We will parse the trace spans and construct the DAG
        spans: list[SpanRecord] = trace.spans

        # 1. First Pass: Create nodes for all spans (Execution Event Nodes)
        for span in spans:
            node_type = self._map_component_to_node_type(span.component_type)

            node_id = f"event:{span.span_id}"
            version_id = str(span.component_version_id) if span.component_version_id else None

            # Fetch version features if available
            features = {}
            if version_id:
                version_record = await self.registry.get_version(trace.tenant_id, UUID(version_id))
                if version_record:
                    features["state"] = version_record.state.value

            if span.latency_ms is not None:
                features["latency_ms"] = span.latency_ms

            node = GraphNode(
                id=node_id,
                type=node_type,
                label=span.name or "unnamed_span",
                is_versioned=bool(version_id),
                version_id=UUID(version_id) if version_id else None,
                span_id=span.span_id,
                features=features,
            )
            nodes[node_id] = node

            # 2. Add structural nodes if this component is versioned (Immutable Component Nodes)
            if version_id:
                comp_node_id = f"version:{version_id}"
                if comp_node_id not in nodes:
                    comp_node = GraphNode(
                        id=comp_node_id,
                        type=node_type,
                        label=f"{span.name} (v)",
                        is_versioned=True,
                        version_id=UUID(version_id),
                        span_id=None,
                        features=features,
                    )
                    nodes[comp_node_id] = comp_node

                # Connect execution event -> version node
                edges.append(
                    GraphEdge(
                        id=f"{node_id}->{comp_node_id}",
                        source=node_id,
                        target=comp_node_id,
                        type=EdgeType.VERSION_LINEAGE,
                        label="instance_of",
                    )
                )

        # 3. Second Pass: Create temporal/causal edges
        span_by_id = {s.span_id: s for s in spans}
        for span in spans:
            node_id = f"event:{span.span_id}"
            parent_id = span.parent_span_id
            if parent_id and parent_id in span_by_id:
                parent_node_id = f"event:{parent_id}"
                # Control flow edge from parent to child
                edges.append(
                    GraphEdge(
                        id=f"{parent_node_id}->{node_id}",
                        source=parent_node_id,
                        target=node_id,
                        type=EdgeType.CONTROL_FLOW,
                        label="calls",
                    )
                )

            # If there's an evidence citation or memory influence in attributes, extract it
            attrs = span.attributes or {}
            if "dgx.memory.referenced" in attrs:
                mem_id = attrs["dgx.memory.referenced"]
                edges.append(
                    GraphEdge(
                        id=f"memory:{mem_id}->{node_id}",
                        source=f"memory:{mem_id}",
                        target=node_id,
                        type=EdgeType.MEMORY_INFLUENCE,
                        label="recalls",
                    )
                )
                # Add memory node if missing
                if f"memory:{mem_id}" not in nodes:
                    nodes[f"memory:{mem_id}"] = GraphNode(
                        id=f"memory:{mem_id}",
                        type=NodeType.MEMORY,
                        label="Memory Store",
                    )

            if "dgx.agent.message_to" in attrs:
                target_agent_id = attrs["dgx.agent.message_to"]
                target_node_id = f"agent:{target_agent_id}"

                edges.append(
                    GraphEdge(
                        id=f"{node_id}->{target_node_id}",
                        source=node_id,
                        target=target_node_id,
                        type=EdgeType.INTER_AGENT_COMMUNICATION,
                        label="messages",
                    )
                )
                # Add target agent node if missing
                if target_node_id not in nodes:
                    nodes[target_node_id] = GraphNode(
                        id=target_node_id,
                        type=NodeType.AGENT,
                        label=f"Agent ({target_agent_id})",
                    )

        # Build the final graph object
        graph = CausalGraph(
            tenant_id=trace.tenant_id,
            run_id=trace.run_id,
            nodes=list(nodes.values()),
            edges=edges,
            builder_version=BUILDER_VERSION,
            trace_digest=getattr(trace, "trace_digest", "unknown"),
        )
        return graph

    def _map_component_to_node_type(self, component_type: str | None) -> NodeType:
        if not component_type:
            return NodeType.OPERATIONAL_RESOURCE

        mapping = {
            "retriever": NodeType.RETRIEVER,
            "generator": NodeType.MODEL,
            "prompt": NodeType.PROMPT,
            "tool_call": NodeType.TOOL,
            "guardrail": NodeType.GUARDRAIL,
            "policy": NodeType.POLICY,
            "agent": NodeType.AGENT,
        }
        return mapping.get(component_type.lower(), NodeType.OPERATIONAL_RESOURCE)
