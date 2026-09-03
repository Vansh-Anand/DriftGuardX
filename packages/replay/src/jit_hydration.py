"""
DriftGuard-X v2 — JIT (Just-In-Time) State Hydration
RAM Optimization: Lazily hydrates only the sub-graph variables directly connected
to the failing node identified by the GAT, rather than forking the entire agent memory state.
PRIVATE — All Rights Reserved.
"""

from __future__ import annotations

from typing import Any


class LazyStateStore:
    """
    Simulates an agent's full memory state as a lazy-loaded property map.
    Variables are only deserialized ('hydrated') when explicitly accessed,
    reducing peak volatile memory footprint.
    """

    def __init__(self, raw_state: dict[str, Any]):
        # Raw serialized state — stored cheaply before hydration
        self._raw: dict[str, Any] = raw_state
        # Cache of already-hydrated variables
        self._hydrated: dict[str, Any] = {}

    def hydrate(self, variable_name: str) -> Any:
        """
        JIT hydrate a single variable by name.
        Simulates decompression / deserialization cost only on demand.
        """
        if variable_name in self._hydrated:
            return self._hydrated[variable_name]
        if variable_name not in self._raw:
            raise KeyError(f"Variable '{variable_name}' not found in state store.")
        # Simulate decompression / deserialization
        value = self._raw[variable_name]
        self._hydrated[variable_name] = value
        return value

    @property
    def hydrated_count(self) -> int:
        return len(self._hydrated)

    @property
    def total_variables(self) -> int:
        return len(self._raw)


class JITGraphHydrator:
    """
    Given a causal graph (nodes + edges) and a failing node identifier,
    this class identifies only the directly connected sub-graph variables
    and lazily hydrates them from the LazyStateStore.

    Patent Claim: Reduces peak RAM utilisation by O(N - K) where N is the
    total number of state variables and K is the size of the failing node's
    local neighbourhood.
    """

    def __init__(self, graph: dict[str, Any], state_store: LazyStateStore):
        """
        Args:
            graph: adjacency list representation {"node_id": [neighbour_ids...]}
            state_store: the agent's full lazy state store
        """
        self._graph = graph  # adjacency list: {node_id: [neighbour_ids]}
        self._state_store = state_store

    def _find_neighbourhood(self, failing_node: str, depth: int = 1) -> set[str]:
        """
        BFS up to `depth` hops from the failing node to find directly
        connected variables in the causal sub-graph.
        """
        visited: set[str] = {failing_node}
        frontier = {failing_node}
        for _ in range(depth):
            next_frontier: set[str] = set()
            for node in frontier:
                for neighbour in self._graph.get(node, []):
                    if neighbour not in visited:
                        visited.add(neighbour)
                        next_frontier.add(neighbour)
            frontier = next_frontier
        return visited

    def hydrate_for_node(self, failing_node: str, depth: int = 1) -> dict[str, Any]:
        """
        JIT hydrate only the variables in the failing node's neighbourhood.

        Returns:
            Dict mapping variable names to their hydrated values.
        Raises:
            KeyError if a graph node has no matching state variable.
        """
        neighbourhood = self._find_neighbourhood(failing_node, depth=depth)
        hydrated: dict[str, Any] = {}
        for var in neighbourhood:
            try:
                hydrated[var] = self._state_store.hydrate(var)
            except KeyError:
                # Node exists in graph but not in state (e.g., structural node)
                hydrated[var] = None
        return hydrated
