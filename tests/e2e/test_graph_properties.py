"""
DriftGuard-X v2 — Graph Property Tests
"""
import pytest
from uuid import uuid4
from packages.contracts.src.graph import CausalGraph, GraphNode, GraphEdge, NodeType, EdgeType
from packages.graph.src.validation import GraphValidator, GraphValidationError

def test_graph_hash_deterministic():
    """Verify that identical graphs produce identical hashes."""
    tenant_id = uuid4()
    run_id = uuid4()
    
    # Base graph creation
    def create_graph():
        return CausalGraph(
            tenant_id=tenant_id,
            run_id=run_id,
            nodes=[
                GraphNode(id="event:1", type=NodeType.QUERY, label="query_1"),
                GraphNode(id="event:2", type=NodeType.RETRIEVER, label="retriever_1")
            ],
            edges=[
                GraphEdge(id="event:1->event:2", source="event:1", target="event:2", type=EdgeType.CONTROL_FLOW)
            ],
            trace_digest="digest_123"
        )
        
    g1 = create_graph()
    g2 = create_graph()
    
    assert g1.graph_hash == g2.graph_hash
    
    # Modifying a property changes the hash
    g3 = create_graph()
    g3.nodes[0].label = "changed_label" 
    # But wait, our graph hash logic only normalizes nodes by ID and edges by Source->Target:Type!
    # So g3 will actually have the SAME hash unless we change ID or edges. 
    # Let's change an edge.
    g4 = CausalGraph(
        tenant_id=tenant_id,
        run_id=run_id,
        nodes=g1.nodes,
        edges=[
            GraphEdge(id="event:1->event:2", source="event:1", target="event:2", type=EdgeType.DATA_DEPENDENCY)
        ],
        trace_digest="digest_123"
    )
    
    assert g1.graph_hash != g4.graph_hash

def test_graph_validation_orphans():
    graph = CausalGraph(
        tenant_id=uuid4(),
        run_id=uuid4(),
        nodes=[
            GraphNode(id="event:1", type=NodeType.QUERY, label="query_1"),
            GraphNode(id="event:2", type=NodeType.RETRIEVER, label="retriever_1")
        ],
        edges=[],  # Empty edges means both are orphans
        trace_digest="digest"
    )
    
    with pytest.raises(GraphValidationError, match="Orphan node"):
        GraphValidator.validate(graph)

def test_graph_validation_cycles():
    graph = CausalGraph(
        tenant_id=uuid4(),
        run_id=uuid4(),
        nodes=[
            GraphNode(id="event:1", type=NodeType.QUERY, label="query_1"),
            GraphNode(id="event:2", type=NodeType.RETRIEVER, label="retriever_1")
        ],
        edges=[
            GraphEdge(id="e1", source="event:1", target="event:2", type=EdgeType.CONTROL_FLOW),
            GraphEdge(id="e2", source="event:2", target="event:1", type=EdgeType.DATA_DEPENDENCY)
        ],
        trace_digest="digest"
    )
    
    with pytest.raises(GraphValidationError, match="cycle"):
        GraphValidator.validate(graph)
        
def test_graph_validation_permitted_cycles():
    graph = CausalGraph(
        tenant_id=uuid4(),
        run_id=uuid4(),
        nodes=[
            GraphNode(id="event:1", type=NodeType.MEMORY, label="memory_1"),
            GraphNode(id="event:2", type=NodeType.MODEL, label="model_1")
        ],
        edges=[
            GraphEdge(id="e1", source="event:1", target="event:2", type=EdgeType.MEMORY_INFLUENCE),
            GraphEdge(id="e2", source="event:2", target="event:1", type=EdgeType.MEMORY_INFLUENCE)
        ],
        trace_digest="digest"
    )
    
    # Memory loops are permitted, so this should not raise an error
    assert GraphValidator.validate(graph) is True
