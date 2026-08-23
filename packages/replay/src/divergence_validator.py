"""
DriftGuard-X v2 — Dynamic Causal Divergence Validator
PRIVATE — All Rights Reserved.

Compares original vs replay execution state:
- Validates causal reachability against the ReplayEquivalenceEnvelope
- Applies per-variable tolerance rules (numeric delta or exact hash match)
- Detects frozen-state violations immediately
- Can terminate invalid replay early when forbidden divergence nodes are reached
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from packages.contracts.src.interfaces import DivergenceReport
from packages.contracts.src.recovery_models import ReplayEquivalenceEnvelope


def _stable_hash(value: Any) -> str:
    """Deterministic SHA-256 of any JSON-serialisable value."""
    serialised = json.dumps(value, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(serialised).hexdigest()


class NodeState:
    """Snapshot of a single node's output at execution time."""

    def __init__(self, node_id: str, output: Any, component_type: str = "") -> None:
        self.node_id = node_id
        self.output = output
        self.component_type = component_type
        self.output_hash = _stable_hash(output)


class ExecutionSnapshot:
    """
    Captures the full per-node state of a pipeline execution.
    Built from span records or replay output dictionaries.
    """

    def __init__(self, nodes: dict[str, NodeState] | None = None) -> None:
        self._nodes: dict[str, NodeState] = nodes or {}

    @classmethod
    def from_spans(cls, spans: list[dict[str, Any]]) -> "ExecutionSnapshot":
        nodes = {}
        for span in spans:
            node_id = span.get("span_id", span.get("node_id", ""))
            if node_id:
                nodes[node_id] = NodeState(
                    node_id=node_id,
                    output=span.get("output", {}),
                    component_type=span.get("component_type", ""),
                )
        return cls(nodes=nodes)

    @classmethod
    def from_replay_result(cls, replay_result: dict[str, Any]) -> "ExecutionSnapshot":
        spans = replay_result.get("spans", replay_result.get("trace", []))
        return cls.from_spans(spans)

    def get_node(self, node_id: str) -> NodeState | None:
        return self._nodes.get(node_id)

    def all_node_ids(self) -> set[str]:
        return set(self._nodes.keys())


def _check_tolerance(
    node_id: str,
    original_val: Any,
    replay_val: Any,
    constraints: dict[str, Any],
) -> tuple[bool, str]:
    """
    Returns (passes, reason).
    Supports: 'exact' (hash equality) and 'numeric_delta' (absolute difference).
    """
    constraint = constraints.get(node_id, constraints.get("*"))
    if constraint is None:
        # Default: exact match
        if _stable_hash(original_val) != _stable_hash(replay_val):
            return False, f"Node {node_id}: exact match failed (no tolerance rule defined)"
        return True, ""

    tolerance_type = constraint.get("type", "exact")

    if tolerance_type == "exact":
        if _stable_hash(original_val) != _stable_hash(replay_val):
            return False, f"Node {node_id}: exact match failed"
        return True, ""

    if tolerance_type == "numeric_delta":
        threshold = float(constraint.get("threshold", 0.0))
        try:
            orig_num = float(original_val) if not isinstance(original_val, (int, float)) else original_val
            replay_num = float(replay_val) if not isinstance(replay_val, (int, float)) else replay_val
            delta = abs(orig_num - replay_num)
            if delta > threshold:
                return False, f"Node {node_id}: numeric delta {delta:.6f} exceeds threshold {threshold}"
            return True, ""
        except (TypeError, ValueError):
            # Can't convert — fall back to hash equality
            if _stable_hash(original_val) != _stable_hash(replay_val):
                return False, f"Node {node_id}: numeric tolerance check fell back to hash; mismatch"
            return True, ""

    if tolerance_type == "ignore":
        return True, ""

    return False, f"Node {node_id}: unknown tolerance type '{tolerance_type}'"


class DynamicCausalDivergenceValidator:
    """
    Compares original execution state vs replay execution state,
    guided by the ReplayEquivalenceEnvelope's causal model.

    Validation logic:
    1. Frozen variable check  — any change is a hard violation
    2. Forbidden divergence   — immediate early termination
    3. Causal reachability    — only allowed_causal_descendants may change
    4. Tolerance rules        — per-variable numeric delta or exact match
    """

    def validate(
        self,
        original: ExecutionSnapshot,
        replay: ExecutionSnapshot,
        envelope: ReplayEquivalenceEnvelope,
    ) -> DivergenceReport:
        """
        Full divergence validation.
        Returns a DivergenceReport — valid=True means the replay is causally coherent.
        """
        per_node: dict[str, Any] = {}
        violated_frozen: list[str] = []
        violated_forbidden: list[str] = []
        early_terminated = False

        all_node_ids = original.all_node_ids() | replay.all_node_ids()
        intervened = set(envelope.intervened_variables)
        allowed_descendants = set(envelope.allowed_causal_descendants)
        forbidden = set(envelope.forbidden_divergence_nodes)
        frozen_vars = envelope.frozen_variables  # node_id -> expected_hash
        constraints = envelope.constraints

        for node_id in sorted(all_node_ids):
            orig_node = original.get_node(node_id)
            replay_node = replay.get_node(node_id)

            orig_val = orig_node.output if orig_node else None
            replay_val = replay_node.output if replay_node else None
            orig_hash = orig_node.output_hash if orig_node else ""
            replay_hash = replay_node.output_hash if replay_node else ""

            changed = orig_hash != replay_hash

            # Skip nodes that were intervened (expected to change)
            if node_id in intervened:
                per_node[node_id] = {
                    "status": "intervened",
                    "changed": changed,
                }
                continue

            # 1. Frozen variable check
            if node_id in frozen_vars:
                expected_hash = frozen_vars[node_id]
                if replay_hash != expected_hash:
                    violated_frozen.append(node_id)
                    per_node[node_id] = {
                        "status": "frozen_violation",
                        "expected_hash": expected_hash,
                        "actual_hash": replay_hash,
                    }
                    # Frozen violations always mean the replay is invalid
                    continue

            if not changed:
                per_node[node_id] = {"status": "unchanged", "valid": True}
                continue

            # 2. Forbidden divergence — early termination
            if node_id in forbidden:
                violated_forbidden.append(node_id)
                early_terminated = True
                per_node[node_id] = {
                    "status": "forbidden_divergence",
                    "orig_hash": orig_hash,
                    "replay_hash": replay_hash,
                }
                # Do not continue checking — terminate immediately
                break

            # 3. Causal reachability check
            if node_id not in allowed_descendants:
                # This node changed but it's not an allowed downstream effect
                # Check tolerance before rejecting
                passes, reason = _check_tolerance(node_id, orig_val, replay_val, constraints)
                if not passes:
                    per_node[node_id] = {
                        "status": "unexpected_divergence",
                        "reason": reason,
                        "orig_hash": orig_hash,
                        "replay_hash": replay_hash,
                    }
                else:
                    per_node[node_id] = {
                        "status": "within_tolerance",
                        "orig_hash": orig_hash,
                        "replay_hash": replay_hash,
                    }
                continue

            # 4. Within allowed descendants — change is expected by the causal model.
            # Only apply a tolerance check if a specific constraint is defined;
            # otherwise the change is unconditionally permitted (that's the point of
            # declaring a node as an allowed_causal_descendant).
            constraint = constraints.get(node_id) or constraints.get("*")
            if constraint is not None:
                passes, reason = _check_tolerance(node_id, orig_val, replay_val, constraints)
                status = "allowed_descendant_changed" if passes else "allowed_descendant_violation"
            else:
                passes = True
                reason = ""
                status = "allowed_descendant_changed"
            per_node[node_id] = {
                "status": status,
                "valid": passes,
                "reason": reason if not passes else "",
                "orig_hash": orig_hash,
                "replay_hash": replay_hash,
            }

        # Determine overall validity
        has_frozen_violations = len(violated_frozen) > 0
        has_forbidden_violations = len(violated_forbidden) > 0
        has_unexpected_divergences = any(
            v.get("status") == "unexpected_divergence" for v in per_node.values()
        )
        has_descendant_violations = any(
            v.get("status") == "allowed_descendant_violation" for v in per_node.values()
        )

        valid = not (
            has_frozen_violations
            or has_forbidden_violations
            or has_unexpected_divergences
            or has_descendant_violations
        )

        reasons = []
        if has_frozen_violations:
            reasons.append(f"Frozen variable violations: {violated_frozen}")
        if has_forbidden_violations:
            reasons.append(f"Forbidden divergence nodes reached: {violated_forbidden}")
        if has_unexpected_divergences:
            bad = [k for k, v in per_node.items() if v.get("status") == "unexpected_divergence"]
            reasons.append(f"Unexpected divergence in non-descendant nodes: {bad}")
        if has_descendant_violations:
            bad = [k for k, v in per_node.items() if v.get("status") == "allowed_descendant_violation"]
            reasons.append(f"Descendant nodes exceeded tolerance: {bad}")

        return DivergenceReport(
            valid=valid,
            reason="; ".join(reasons) if reasons else "All causal divergence constraints satisfied.",
            per_node=per_node,
            early_terminated=early_terminated,
            violated_frozen_nodes=violated_frozen,
            violated_forbidden_nodes=violated_forbidden,
        )

    def validate_divergence(
        self,
        replays: list[dict[str, Any]],
        envelope: ReplayEquivalenceEnvelope,
    ) -> DivergenceReport:
        """
        Adapter for the orchestrator interface.
        Processes a list of replay results, validating each against the envelope.
        Returns the worst (most restrictive) DivergenceReport.
        """
        if not replays:
            return DivergenceReport(valid=True, reason="No replays to validate.")

        worst: DivergenceReport | None = None
        for replay_result in replays:
            original_spans = replay_result.get("original_spans", [])
            replay_spans = replay_result.get("replay_spans", replay_result.get("spans", []))

            orig_snapshot = ExecutionSnapshot.from_spans(original_spans)
            replay_snapshot = ExecutionSnapshot.from_spans(replay_spans)

            report = self.validate(orig_snapshot, replay_snapshot, envelope)
            if worst is None or (not report.valid and worst.valid):
                worst = report

        return worst or DivergenceReport(valid=True, reason="All replays passed divergence check.")
