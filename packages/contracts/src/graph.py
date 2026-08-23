"""
DriftGuard-X v2 — Graph Data Contracts

Defines the node and edge types for the Causal Reliability Graph.
PRIVATE — All Rights Reserved.
"""
import enum
import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from packages.contracts.src.models import DGXBaseModel, _utcnow


class NodeType(str, enum.Enum):
    REQUEST = "request"
    QUERY = "query"
    RETRIEVER = "retriever"
    INDEX = "index"
    CHUNKER = "chunker"
    RERANKER = "reranker"
    PROMPT = "prompt"
    MODEL = "model"
    MEMORY = "memory"
    GUARDRAIL = "guardrail"
    TOOL = "tool"
    POLICY = "policy"
    HUMAN_APPROVAL = "human_approval"
    PROVIDER = "provider"
    OPERATIONAL_RESOURCE = "operational_resource"
    AGENT = "agent"


class EdgeType(str, enum.Enum):
    # ── Original values — DO NOT RENAME ──
    DATA_DEPENDENCY = "data_dependency"
    CONTROL_FLOW = "control_flow"           # temporal ordering (not strictly causal)
    VERSION_LINEAGE = "version_lineage"
    POLICY_DEPENDENCY = "policy_dependency"
    MEMORY_INFLUENCE = "memory_influence"
    EVIDENCE_CITATION = "evidence_citation"
    TOOL_EFFECT = "tool_effect"
    RETRY_FALLBACK = "retry_fallback"
    INTER_AGENT_COMMUNICATION = "inter_agent_communication"

    # ── Extended causal edge types (additive) ──
    # These must be set explicitly; CONTROL_FLOW must NOT be auto-promoted to causal.
    CONTROL_DEPENDENCY = "control_dependency"  # explicitly causal control path
    MEMORY_DEPENDENCY = "memory_dependency"    # memory read causes downstream output
    TOOL_DEPENDENCY = "tool_dependency"        # tool result determines downstream
    DERIVED_DEPENDENCY = "derived_dependency"  # computed/derived value dependency
    UNKNOWN_DEPENDENCY = "unknown_dependency"  # causal relationship unknown; do not fabricate


class GraphNode(DGXBaseModel):
    id: str = Field(min_length=1)  # Format: {type}:{version_id} or {type}:{span_id}
    type: NodeType
    label: str
    
    # Core attributes
    is_versioned: bool = False
    version_id: Optional[UUID] = None
    span_id: Optional[str] = None
    
    # Baseline Features
    features: Dict[str, Any] = Field(default_factory=dict)
    # Examples: local_quality, latency_ms, cost_usd, error_code, version_age_days
    
    created_at: datetime = Field(default_factory=_utcnow)


class GraphEdge(DGXBaseModel):
    id: str = Field(min_length=1)  # Format: {source_id}->{target_id}
    source: str
    target: str
    type: EdgeType
    label: str = ""
    properties: Dict[str, Any] = Field(default_factory=dict)


class CausalGraph(DGXBaseModel):
    tenant_id: UUID
    run_id: UUID
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    builder_version: str = "v1"
    trace_digest: str  # Hash of the original trace
    graph_hash: str = "" # hash(trace_digest, builder_version, normalized nodes/edges)
    created_at: datetime = Field(default_factory=_utcnow)

    @model_validator(mode="after")
    def compute_graph_hash(self) -> "CausalGraph":
        """Compute the deterministic identity of this graph."""
        nodes_normalized = sorted(
            [n.id for n in self.nodes]
        )
        edges_normalized = sorted(
            [f"{e.source}->{e.target}:{e.type.value if hasattr(e.type, 'value') else e.type}" for e in self.edges]
        )
        
        payload = {
            "trace_digest": self.trace_digest,
            "builder_version": self.builder_version,
            "nodes": nodes_normalized,
            "edges": edges_normalized
        }
        
        serialized = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.graph_hash = hashlib.sha256(serialized).hexdigest()
        return self
