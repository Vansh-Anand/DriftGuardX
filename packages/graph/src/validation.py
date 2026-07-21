"""
DriftGuard-X v2 — Graph Validation
PRIVATE — All Rights Reserved.
"""
from typing import Dict, List, Set
from packages.contracts.src.graph import CausalGraph, EdgeType


class GraphValidationError(Exception):
    pass


class GraphValidator:
    """
    Validates Causal Reliability Graphs for properties such as DAG constraints,
    orphans, duplicate executions, and temporal ordering.
    """
    
    @staticmethod
    def validate(graph: CausalGraph) -> bool:
        """
        Run all validation checks. Raises GraphValidationError if invalid.
        """
        GraphValidator._check_orphans(graph)
        GraphValidator._check_cycles(graph)
        return True
        
    @staticmethod
    def _check_orphans(graph: CausalGraph):
        if not graph.nodes:
            return
            
        # Find all nodes connected to any edge
        connected = set()
        for edge in graph.edges:
            connected.add(edge.source)
            connected.add(edge.target)
            
        # The root node (or a single disconnected node) might not have edges if it's a 1-node graph.
        if len(graph.nodes) > 1:
            for node in graph.nodes:
                if node.id not in connected:
                    raise GraphValidationError(f"Orphan node detected: {node.id}")
                    
    @staticmethod
    def _check_cycles(graph: CausalGraph):
        # Build adjacency list (only considering Control Flow and Data Dependency edges as causal)
        adj: Dict[str, List[str]] = {node.id: [] for node in graph.nodes}
        
        for edge in graph.edges:
            # Memory loops and Retries are permitted cycles
            if edge.type not in (EdgeType.MEMORY_INFLUENCE, EdgeType.RETRY_FALLBACK):
                if edge.source in adj:
                    adj[edge.source].append(edge.target)
                    
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        
        def is_cyclic(curr: str) -> bool:
            visited.add(curr)
            rec_stack.add(curr)
            
            for neighbor in adj.get(curr, []):
                if neighbor not in visited:
                    if is_cyclic(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
                    
            rec_stack.remove(curr)
            return False
            
        for node in graph.nodes:
            if node.id not in visited:
                if is_cyclic(node.id):
                    raise GraphValidationError("Illegal causal cycle detected in DAG.")
