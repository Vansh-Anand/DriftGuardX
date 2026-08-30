"""
DriftGuard-X v2 — Causal Recovery Cut
PRIVATE — All Rights Reserved.
"""
import hashlib
import json
from itertools import combinations

from packages.contracts.src.graph import CausalGraph
from packages.contracts.src.recovery_models import (
    CausalRecoveryCut,
    FailureTarget,
    FaultSource,
    OptimizationMethod,
    RecoveryAction,
)


class FailurePathEnumerator:
    """Finds all directed paths from FaultSources to FailureTargets in a CausalGraph."""

    def __init__(self, graph: CausalGraph):
        self.graph = graph
        # Build adjacency list: node_id -> list of target_node_ids
        self.adj: dict[str, list[str]] = {node.id: [] for node in graph.nodes}
        for edge in graph.edges:
            if edge.source in self.adj:
                self.adj[edge.source].append(edge.target)

    def enumerate_paths(
        self, sources: list[FaultSource], targets: list[FailureTarget]
    ) -> list[list[str]]:
        """
        Returns a list of node paths (each path is a list of node_ids).
        Uses DFS to find all paths from any source to any target.
        """
        source_ids = {s.node_id for s in sources}
        target_ids = {t.node_id for t in targets}

        all_paths: list[list[str]] = []

        for start_node in source_ids:
            if start_node not in self.adj:
                continue

            stack = [(start_node, [start_node])]

            while stack:
                curr, path = stack.pop()
                if curr in target_ids:
                    all_paths.append(path)

                for neighbor in self.adj.get(curr, []):
                    if neighbor not in path:  # Avoid cycles
                        stack.append((neighbor, path + [neighbor]))

        return all_paths


class CutOptimizer:
    """Computes the Minimum Causal Recovery Cut (Hitting Set problem)."""

    # Heuristic limit: if branching exceeds this many combinations, switch to GREEDY
    MAX_EXACT_COMBINATIONS = 10000

    def __init__(self, available_actions: list[RecoveryAction]):
        self.available_actions = available_actions

    def _cost(self, action: RecoveryAction) -> float:
        # Simple weighted sum (can be customized)
        return (
            action.change_cost * 1.0 +
            action.blast_radius * 1.5 +
            action.regression_risk * 2.0 +
            action.expected_downtime * 0.5
        )

    def optimize(
        self,
        paths: list[list[str]],
        sources: list[FaultSource],
        targets: list[FailureTarget]
    ) -> CausalRecoveryCut:
        """
        Finds the optimal set of actions to 'hit' (block) every path.
        An action 'hits' a path if the action's target_component is in the path.
        """
        # Mapping: action_id -> set of path indices it hits
        action_coverage: dict[str, set[int]] = {}
        for action in self.available_actions:
            hits = set()
            for i, path in enumerate(paths):
                if action.target_component in path:
                    hits.add(i)
            action_coverage[action.action_id] = hits

        num_paths = len(paths)
        if num_paths == 0:
            return self._build_cut([], paths, [], sources, targets, OptimizationMethod.EXACT)

        # Filter out actions that don't hit any paths
        useful_actions = [a for a in self.available_actions if action_coverage[a.action_id]]

        best_combo: tuple[RecoveryAction, ...] | None = None
        best_cost = float('inf')

        # Check if we should use exact branch-and-bound/combinations or greedy heuristic
        total_combos = sum(1 for k in range(1, len(useful_actions) + 1)
                           for _ in combinations(useful_actions, k))

        if total_combos <= self.MAX_EXACT_COMBINATIONS:
            opt_method = OptimizationMethod.EXACT
            # Try combinations of increasing size
            for r in range(1, len(useful_actions) + 1):
                for combo in combinations(useful_actions, r):
                    covered = set()
                    for act in combo:
                        covered.update(action_coverage[act.action_id])

                    if len(covered) == num_paths:
                        cost = sum(self._cost(a) for a in combo)
                        if cost < best_cost:
                            best_cost = cost
                            best_combo = combo
        else:
            opt_method = OptimizationMethod.APPROXIMATE
            # Greedy Set Cover
            uncovered = set(range(num_paths))
            selected_actions = []
            while uncovered:
                # Pick action that covers most uncovered paths for lowest cost
                best_action = None
                best_ratio = -1.0

                for act in useful_actions:
                    if act in selected_actions:
                        continue
                    covered_by_act = action_coverage[act.action_id].intersection(uncovered)
                    if not covered_by_act:
                        continue

                    cost = self._cost(act)
                    # Small epsilon to avoid division by zero
                    ratio = len(covered_by_act) / (cost + 1e-5)
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_action = act

                if not best_action:
                    break # Cannot cover remaining paths

                selected_actions.append(best_action)
                uncovered -= action_coverage[best_action.action_id]

            if not uncovered:
                best_combo = tuple(selected_actions)

        # Build output
        selected_list: list[RecoveryAction] = list(best_combo) if best_combo else []
        blocked: list[list[str]] = []
        residual: list[list[str]] = []

        if selected_list:
            blocked = paths
            residual = []
        else:
            blocked = []
            residual = paths

        return self._build_cut(selected_list, blocked, residual, sources, targets, opt_method)

    def _build_cut(
        self,
        selected_actions: list[RecoveryAction],
        blocked_paths: list[list[str]],
        residual_paths: list[list[str]],
        sources: list[FaultSource],
        targets: list[FailureTarget],
        opt_method: OptimizationMethod
    ) -> CausalRecoveryCut:

        t_cost = sum(a.change_cost for a in selected_actions)
        t_blast = sum(a.blast_radius for a in selected_actions)
        t_risk = sum(a.regression_risk for a in selected_actions)
        t_down = sum(a.expected_downtime for a in selected_actions)

        # Simple evidence hash based on targets and sources
        evidence_payload = json.dumps({
            "targets": [t.node_id for t in targets],
            "sources": [s.node_id for s in sources],
            "actions": [a.action_id for a in selected_actions]
        }, sort_keys=True)
        evidence_hash = hashlib.sha256(evidence_payload.encode()).hexdigest()

        return CausalRecoveryCut(
            fault_sources=sources,
            failure_targets=targets,
            selected_actions=selected_actions,
            blocked_failure_paths=blocked_paths,
            residual_failure_paths=residual_paths,
            total_change_cost=t_cost,
            blast_radius=t_blast,
            regression_risk=t_risk,
            expected_downtime=t_down,
            optimization_method=opt_method,
            evidence_hash=evidence_hash
        )
