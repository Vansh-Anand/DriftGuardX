"""
DriftGuard-X v2 — Graph API Models
PRIVATE — All Rights Reserved.
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from apps.api.src.database import Base


class CausalGraphORM(Base):
    """
    Persisted snapshot of a Causal Reliability Graph.
    """
    __tablename__ = "causal_graphs"
    
    # Using graph_hash as the primary key since it's deterministic based on inputs
    graph_hash = Column(String(64), primary_key=True)
    tenant_id = Column(String(36), index=True, nullable=False)
    run_id = Column(String(36), index=True, nullable=False)
    trace_digest = Column(String(64), nullable=False)
    builder_version = Column(String(32), nullable=False)
    
    # Store nodes and edges as JSON for snapshot retrieval
    # For complex relational queries, an edge adjacency table is also used
    nodes_json = Column(JSON, nullable=False)
    edges_json = Column(JSON, nullable=False)
    
    created_at = Column(DateTime(timezone=True), nullable=False)


class GraphEdgeORM(Base):
    """
    Relational edge storage to support recursive CTE traversals and neighbor queries.
    """
    __tablename__ = "graph_edges"
    
    id = Column(String(128), primary_key=True) # {graph_hash}:{source}->{target}
    graph_hash = Column(String(64), ForeignKey("causal_graphs.graph_hash"), index=True, nullable=False)
    
    source_id = Column(String(128), index=True, nullable=False)
    target_id = Column(String(128), index=True, nullable=False)
    
    edge_type = Column(String(32), nullable=False)
    label = Column(String(128), nullable=True)
    properties_json = Column(JSON, nullable=False)
    
    graph = relationship("CausalGraphORM", backref="persisted_edges")
