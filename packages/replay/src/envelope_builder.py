"""
DriftGuard-X v2 — Replay Equivalence Envelope Builder

Constructs a ReplayEquivalenceEnvelope given:
  - original trace (TraceArtifact)
  - causal graph (CausalGraph)
  - candidate intervention (CausalIntervention)
  - execution state snapshot (ExecutionStateSnapshot)
  - runtime policy version

The builder:
  1. Validates the intervention component exists in the graph.
  2. Computes the causal descendants of the intervention node.
  3. Classifies every variable as frozen, intervened, endogenous,
     exogenous, or nondeterministic.
  4. Builds equivalence constraints for frozen variables.
  5. Assembles the envelope with cryptographic binding.

PRIVATE — All Rights Reserved.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from packages.contracts.src.envelope import (
    CausalIntervention,
    EquivalenceConstraint,
    EquivalenceConstraintType,
    ReplayEquivalenceEnvelope,
)
from packages.contracts.src.exogenous import (
    ExogenousReplayStrategy,
    ExogenousStateRecord,
    ExogenousSourceType,
)
from packages.contracts.src.execution_state import (
    ExecutionStateSnapshot,
    ExecutionStateValue,
    ExecutionVariableClass,
)
from packages.contracts.src.graph import CausalGraph, EdgeType, GraphEdge


# ─── Edge types that propagate causal effects ────────────────────────────────

_CAUSAL_EDGE_TYPES = frozenset({
    EdgeType.DATA_DEPENDENCY,
    EdgeType.CONTROL_FLOW,          # temporal → treated as potential causal path
    EdgeType.CONTROL_DEPENDENCY,    # explicitly causal
    EdgeType.MEMORY_INFLUENCE,
    EdgeType.MEMORY_DEPENDENCY,
    EdgeType.TOOL_EFFECT,
    EdgeType.TOOL_DEPENDENCY,
    EdgeType.DERIVED_DEPENDENCY,
    EdgeType.POLICY_DEPENDENCY,
    EdgeType.INTER_AGENT_COMMUNICATION,
    # VERSION_LINEAGE, EVIDENCE_CITATION, RETRY_FALLBACK are excluded:
    # they are structural, not data-flow causal.
})

# ─── Variable keys that default to EXACT_HASH constraint ─────────────────────

_SECURITY_CRITICAL_KEYS = frozenset({
    "policy_hash", "tool_schema", "random_seed", "authorization_context_hash",
    "container_image_digest", "dependency_lockfile_hash",
})


# ─── Validation Errors ───────────────────────────────────────────────────────

class EnvelopeValidationError(ValueError):
    """Raised when envelope construction violates causal experiment rules."""
    pass


# ─── Builder ──────────────────────────────────────────────────────────────────

class ReplayEquivalenceEnvelopeBuilder:
    """
    Builds a validated ReplayEquivalenceEnvelope from typed inputs.

    The builder is stateless — call ``build()`` to produce an envelope.
    """

    def build(
        self,
        *,
        original_trace_id: UUID,
        causal_graph: CausalGraph,
        intervention: CausalIntervention,
        state_snapshot: ExecutionStateSnapshot,
        policy_version: str,
        tenant_id: UUID,
        replay_id: Optional[UUID] = None,
        trusted_timestamp_reference: Optional[str] = None,
        strict_mode: bool = True,
    ) -> ReplayEquivalenceEnvelope:
        """
        Build and validate a ReplayEquivalenceEnvelope.

        Parameters
        ----------
        original_trace_id
            UUID of the original trace this replay is based on.
        causal_graph
            The CausalGraph of the original run.
        intervention
            The single CausalIntervention to apply.
        state_snapshot
            The ExecutionStateSnapshot captured from the original run.
        policy_version
            The policy version governing this experiment.
        tenant_id
            Must match all component identities and the graph.
        replay_id
            Pre-allocated UUID for the replay. Generated if None.
        trusted_timestamp_reference
            Optional trusted time reference identifier.
        strict_mode
            If True, reject replays where exogenous state cannot be reproduced.

        Returns
        -------
        ReplayEquivalenceEnvelope

        Raises
        ------
        EnvelopeValidationError
            If the envelope cannot be constructed due to validation failures.
        """
        if replay_id is None:
            replay_id = uuid4()

        # ── 1. Validate tenant consistency ────────────────────────────────────
        if causal_graph.tenant_id != tenant_id:
            raise EnvelopeValidationError(
                f"Cross-tenant graph: graph tenant {causal_graph.tenant_id} "
                f"does not match requested tenant {tenant_id}."
            )
        if state_snapshot.tenant_id != tenant_id:
            raise EnvelopeValidationError(
                f"Cross-tenant state snapshot: snapshot tenant "
                f"{state_snapshot.tenant_id} does not match {tenant_id}."
            )

        # ── 2. Validate intervention component exists in graph ────────────────
        graph_node_ids = {n.id for n in causal_graph.nodes}
        intervention_node_id = self._find_intervention_node(
            intervention.component_id, causal_graph
        )
        if intervention_node_id is None:
            raise EnvelopeValidationError(
                f"Intervention component '{intervention.component_id}' does not "
                f"exist in the causal graph. Available nodes: "
                f"{sorted(list(graph_node_ids)[:10])}"
            )

        # ── 3. Validate intervention variable exists in snapshot ──────────────
        intervened_sv = state_snapshot.get_value(intervention.variable_key)
        if intervened_sv is None:
            raise EnvelopeValidationError(
                f"Intervention variable '{intervention.variable_key}' not found "
                f"in ExecutionStateSnapshot."
            )
        if intervened_sv.value_hash != intervention.original_value_hash:
            raise EnvelopeValidationError(
                f"Intervention original_value_hash does not match snapshot: "
                f"snapshot has {intervened_sv.value_hash}, intervention declares "
                f"{intervention.original_value_hash}."
            )

        # ── 4. Compute causal descendants ─────────────────────────────────────
        descendant_node_ids = self._compute_causal_descendants(
            intervention_node_id, causal_graph
        )

        # Map node IDs to component identity hashes where available
        allowed_descendant_components = self._nodes_to_component_ids(
            descendant_node_ids, causal_graph, state_snapshot
        )

        # ── 5. Classify variables ─────────────────────────────────────────────
        frozen_keys: list[str] = []
        intervened_keys: list[str] = [intervention.variable_key]
        exogenous_records: list[ExogenousStateRecord] = []
        nondeterministic_keys: list[str] = []
        endogenous_keys: list[str] = []

        for sv in state_snapshot.values:
            if sv.key == intervention.variable_key:
                # Already classified as INTERVENED
                continue

            vc = ExecutionVariableClass(sv.variable_class) \
                if isinstance(sv.variable_class, str) else sv.variable_class

            if vc == ExecutionVariableClass.FROZEN:
                frozen_keys.append(sv.key)

            elif vc == ExecutionVariableClass.INTERVENED:
                # Multiple interventions detected — reject
                raise EnvelopeValidationError(
                    f"Multiple INTERVENED variables detected: "
                    f"'{sv.key}' and '{intervention.variable_key}'. "
                    f"Only one intervention per envelope is allowed."
                )

            elif vc == ExecutionVariableClass.ENDOGENOUS:
                endogenous_keys.append(sv.key)

            elif vc == ExecutionVariableClass.EXOGENOUS:
                strategy = self._select_exogenous_strategy(sv, strict_mode)
                exogenous_records.append(ExogenousStateRecord(
                    state_id=f"{sv.key}_{sv.timestamp.isoformat()}",
                    key=sv.key,
                    source_type=ExogenousSourceType.OTHER,
                    source_identifier=sv.source,
                    original_value_hash=sv.value_hash,
                    replay_strategy=strategy,
                    reproducibility_level="uncontrollable" if strategy in (ExogenousReplayStrategy.UNCONTROLLABLE, ExogenousReplayStrategy.FORBID_REPLAY) else "deterministic",
                    captured_value=None,
                    metadata=sv.metadata
                ))

            elif vc == ExecutionVariableClass.NONDETERMINISTIC:
                nondeterministic_keys.append(sv.key)

            elif vc == ExecutionVariableClass.DERIVED:
                # Derived variables are frozen unless causally downstream
                if sv.component_id and sv.component_id in allowed_descendant_components:
                    endogenous_keys.append(sv.key)
                else:
                    frozen_keys.append(sv.key)

            elif vc == ExecutionVariableClass.UNKNOWN:
                if strict_mode:
                    raise EnvelopeValidationError(
                        f"Variable '{sv.key}' has UNKNOWN classification. "
                        f"Strict mode requires all variables to be classified."
                    )
                nondeterministic_keys.append(sv.key)

        # ── 6. Check for FORBID_REPLAY exogenous variables ────────────────────
        for ev in exogenous_records:
            if ev.replay_strategy == ExogenousReplayStrategy.FORBID_REPLAY:
                raise EnvelopeValidationError(
                    f"Exogenous variable '{ev.key}' requires "
                    f"FORBID_REPLAY strategy. Replay cannot proceed."
                )

        # ── 7. Compute forbidden divergence components ────────────────────────
        # Everything NOT in the descendant set is forbidden from diverging
        forbidden_divergence = self._compute_forbidden_components(
            graph_node_ids, descendant_node_ids, intervention_node_id,
            causal_graph, state_snapshot
        )

        # ── 8. Build equivalence constraints ──────────────────────────────────
        constraints = self._build_constraints(frozen_keys, state_snapshot)

        # ── 9. Check for unresolved critical nodes ────────────────────────────
        self._check_unresolved_nodes(causal_graph, strict_mode)

        # ── 10. Assemble envelope ─────────────────────────────────────────────
        envelope = ReplayEquivalenceEnvelope(
            original_trace_id=original_trace_id,
            replay_id=replay_id,
            tenant_id=tenant_id,
            intervention=intervention,
            original_state_hash=state_snapshot.snapshot_hash,
            frozen_variables=frozen_keys,
            intervened_variables=intervened_keys,
            exogenous_variables=exogenous_records,
            allowed_descendant_components=sorted(allowed_descendant_components),
            forbidden_divergence_components=sorted(forbidden_divergence),
            nondeterministic_variables=nondeterministic_keys,
            equivalence_constraints=constraints,
            policy_version=policy_version,
            trusted_timestamp_reference=trusted_timestamp_reference,
        )

        return envelope

    # ── Internal: find intervention node ──────────────────────────────────────

    def _find_intervention_node(
        self, component_identity_hash: str, graph: CausalGraph
    ) -> str | None:
        """
        Find the graph node that corresponds to the intervention's component_id.

        The component_id (an identity hash) is matched against node features
        where ``features["component_identity_hash"]`` is set, or against the
        node ID directly if it contains the component_id.
        """
        for node in graph.nodes:
            # Primary: match by feature annotation
            if node.features.get("component_identity_hash") == component_identity_hash:
                return node.id
            # Fallback: match by node ID containing the component ID
            if component_identity_hash in node.id:
                return node.id
        return None

    # ── Internal: compute causal descendants ──────────────────────────────────

    def _compute_causal_descendants(
        self, intervention_node_id: str, graph: CausalGraph
    ) -> set[str]:
        """
        BFS over causal edges starting from the intervention node.

        Only edges whose type is in ``_CAUSAL_EDGE_TYPES`` propagate causality.
        The intervention node itself is NOT included in the descendant set
        (it is the intervention, not a consequence).

        Returns the set of node IDs that are causally downstream.
        """
        adjacency: dict[str, list[str]] = {}
        for edge in graph.edges:
            edge_type = EdgeType(edge.type) if isinstance(edge.type, str) else edge.type
            if edge_type in _CAUSAL_EDGE_TYPES:
                adjacency.setdefault(edge.source, []).append(edge.target)

        descendants: set[str] = set()
        queue = deque(adjacency.get(intervention_node_id, []))
        while queue:
            current = queue.popleft()
            if current in descendants:
                continue
            descendants.add(current)
            for child in adjacency.get(current, []):
                if child not in descendants:
                    queue.append(child)

        return descendants

    # ── Internal: map node IDs to component identity hashes ───────────────────

    def _nodes_to_component_ids(
        self,
        node_ids: set[str],
        graph: CausalGraph,
        snapshot: ExecutionStateSnapshot,
    ) -> list[str]:
        """
        Convert graph node IDs to component identity hashes.

        Uses the ``features["component_identity_hash"]`` annotation if present,
        otherwise derives from the node ID itself.
        """
        component_ids: set[str] = set()
        nodes_by_id = {n.id: n for n in graph.nodes}
        for nid in node_ids:
            node = nodes_by_id.get(nid)
            if node is None:
                continue
            cid = node.features.get("component_identity_hash")
            if cid:
                component_ids.add(cid)
            else:
                # Use node ID as fallback component identifier
                component_ids.add(nid)
        return sorted(component_ids)

    # ── Internal: compute forbidden divergence ────────────────────────────────

    def _compute_forbidden_components(
        self,
        all_node_ids: set[str],
        descendant_ids: set[str],
        intervention_node_id: str,
        graph: CausalGraph,
        snapshot: ExecutionStateSnapshot,
    ) -> list[str]:
        """
        Components not in the descendant set and not the intervention itself
        are forbidden from diverging.
        """
        forbidden_nodes = all_node_ids - descendant_ids - {intervention_node_id}
        nodes_by_id = {n.id: n for n in graph.nodes}
        forbidden_cids: set[str] = set()
        for nid in forbidden_nodes:
            node = nodes_by_id.get(nid)
            if node is None:
                continue
            cid = node.features.get("component_identity_hash")
            if cid:
                forbidden_cids.add(cid)
            else:
                forbidden_cids.add(nid)
        return sorted(forbidden_cids)

    # ── Internal: exogenous strategy selection ────────────────────────────────

    def _select_exogenous_strategy(
        self, sv: ExecutionStateValue, strict_mode: bool
    ) -> ExogenousReplayStrategy:
        """
        Select a default handling strategy for an exogenous variable.

        In strict mode, variables marked with capture_failed are rejected.
        Otherwise, they are marked as UNCONTROLLABLE.
        """
        is_missing = sv.metadata.get("capture_failed", False)
        
        if sv.source == "external_api_response_hash":
            if not is_missing:
                return ExogenousReplayStrategy.FREEZE_CAPTURED
            elif strict_mode:
                return ExogenousReplayStrategy.FORBID_REPLAY
            else:
                return ExogenousReplayStrategy.UNCONTROLLABLE

        if sv.source == "trusted_timestamp_metadata":
            return ExogenousReplayStrategy.FREEZE_CAPTURED

        # Default: freeze if we successfully captured it
        if not is_missing:
            return ExogenousReplayStrategy.FREEZE_CAPTURED

        if strict_mode:
            return ExogenousReplayStrategy.FORBID_REPLAY
        return ExogenousReplayStrategy.UNCONTROLLABLE

    # ── Internal: build constraints ───────────────────────────────────────────

    def _build_constraints(
        self, frozen_keys: list[str], snapshot: ExecutionStateSnapshot
    ) -> list[EquivalenceConstraint]:
        """
        Build equivalence constraints for frozen variables.

        Security-critical fields default to EXACT_HASH.
        Version fields default to EXACT_VERSION.
        All others default to EXACT_HASH (conservative).
        """
        constraints: list[EquivalenceConstraint] = []
        for key in frozen_keys:
            if key in _SECURITY_CRITICAL_KEYS:
                ct = EquivalenceConstraintType.EXACT_HASH
                desc = "Security-critical: exact hash match required"
            elif "version" in key.lower():
                ct = EquivalenceConstraintType.EXACT_VERSION
                desc = "Version field: exact version match required"
            else:
                ct = EquivalenceConstraintType.EXACT_HASH
                desc = "Default: exact hash match"

            constraints.append(EquivalenceConstraint(
                variable_key=key,
                constraint_type=ct,
                description=desc,
            ))
        return constraints

    # ── Internal: check for unresolved critical nodes ─────────────────────────

    def _check_unresolved_nodes(
        self, graph: CausalGraph, strict_mode: bool
    ) -> None:
        """
        Check for nodes connected only by UNKNOWN_DEPENDENCY edges.
        In strict mode, these are fatal.
        """
        if not strict_mode:
            return

        for edge in graph.edges:
            edge_type = EdgeType(edge.type) if isinstance(edge.type, str) else edge.type
            if edge_type == EdgeType.UNKNOWN_DEPENDENCY:
                raise EnvelopeValidationError(
                    f"Graph contains UNKNOWN_DEPENDENCY edge: "
                    f"{edge.source} -> {edge.target}. "
                    f"Causal relationship must be resolved before building "
                    f"an equivalence envelope in strict mode."
                )
