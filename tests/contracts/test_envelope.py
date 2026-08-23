"""
Tests for packages/contracts/src/envelope.py
and packages/replay/src/envelope_builder.py

Covers:
  - Retriever intervention
  - Prompt intervention
  - Memory removal
  - Model version change
  - Missing graph node → rejected
  - Invalid descendant set
  - Cross-tenant graph → rejected
  - Frozen variable conflict (frozen ∩ intervened)
  - External API variable
  - Multiple intervention attempt → rejected
  - Tampered envelope detected
  - Hash reproducibility / determinism
  - RAEB envelope-aware admissibility
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from packages.contracts.src.envelope import (
    CausalIntervention,
    CausalInterventionType,
    EquivalenceConstraint,
    EquivalenceConstraintType,
    ExogenousHandlingStrategy,
    ExogenousVariableSpec,
    ReplayEquivalenceEnvelope,
)
from packages.contracts.src.execution_state import (
    ExecutionStateSnapshot,
    ExecutionStateValue,
    ExecutionVariableClass,
    hash_state_value,
)
from packages.contracts.src.graph import (
    CausalGraph,
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeType,
)
from packages.contracts.src.identity import ComponentIdentity
from packages.contracts.src.models import ComponentType
from packages.replay.src.envelope_builder import (
    EnvelopeValidationError,
    ReplayEquivalenceEnvelopeBuilder,
)


# ──────────────────────────────────────────────────────────────────────────────
# Shared Test Fixtures
# ──────────────────────────────────────────────────────────────────────────────

TENANT_ID = uuid4()
RUN_ID = uuid4()
TRACE_ID = uuid4()
TS = datetime(2024, 7, 1, 12, 0, 0, tzinfo=timezone.utc)

# Component identity hashes (deterministic for tests)
RETRIEVER_CID = hashlib.sha256(b"retriever-shard-01").hexdigest()
RERANKER_CID = hashlib.sha256(b"reranker-v1").hexdigest()
PROMPT_CID = hashlib.sha256(b"prompt-template-v3").hexdigest()
MODEL_CID = hashlib.sha256(b"llm-gpt4-v1").hexdigest()
MEMORY_CID = hashlib.sha256(b"memory-store-v1").hexdigest()
POLICY_CID = hashlib.sha256(b"policy-engine-v1").hexdigest()
TOOL_CID = hashlib.sha256(b"tool-web-search-v1").hexdigest()


def _make_graph(
    tenant_id: UUID = TENANT_ID,
    include_unknown_edge: bool = False,
) -> CausalGraph:
    """
    Build a simple pipeline graph:
      Retriever → Reranker → Prompt → Model → Policy
                                          ↑
                                       Memory
    """
    nodes = [
        GraphNode(id=RETRIEVER_CID, type=NodeType.RETRIEVER, label="Retriever",
                  features={"component_identity_hash": RETRIEVER_CID}),
        GraphNode(id=RERANKER_CID, type=NodeType.RERANKER, label="Reranker",
                  features={"component_identity_hash": RERANKER_CID}),
        GraphNode(id=PROMPT_CID, type=NodeType.PROMPT, label="Prompt",
                  features={"component_identity_hash": PROMPT_CID}),
        GraphNode(id=MODEL_CID, type=NodeType.MODEL, label="LLM",
                  features={"component_identity_hash": MODEL_CID}),
        GraphNode(id=MEMORY_CID, type=NodeType.MEMORY, label="Memory",
                  features={"component_identity_hash": MEMORY_CID}),
        GraphNode(id=POLICY_CID, type=NodeType.POLICY, label="Policy",
                  features={"component_identity_hash": POLICY_CID}),
    ]
    edges = [
        GraphEdge(id=f"{RETRIEVER_CID}->{RERANKER_CID}",
                  source=RETRIEVER_CID, target=RERANKER_CID,
                  type=EdgeType.DATA_DEPENDENCY, label="retrieval_output"),
        GraphEdge(id=f"{RERANKER_CID}->{PROMPT_CID}",
                  source=RERANKER_CID, target=PROMPT_CID,
                  type=EdgeType.DATA_DEPENDENCY, label="reranked_docs"),
        GraphEdge(id=f"{PROMPT_CID}->{MODEL_CID}",
                  source=PROMPT_CID, target=MODEL_CID,
                  type=EdgeType.DATA_DEPENDENCY, label="prompt_text"),
        GraphEdge(id=f"{MEMORY_CID}->{MODEL_CID}",
                  source=MEMORY_CID, target=MODEL_CID,
                  type=EdgeType.MEMORY_INFLUENCE, label="context"),
        GraphEdge(id=f"{MODEL_CID}->{POLICY_CID}",
                  source=MODEL_CID, target=POLICY_CID,
                  type=EdgeType.CONTROL_FLOW, label="output_check"),
    ]
    if include_unknown_edge:
        edges.append(GraphEdge(
            id=f"{TOOL_CID}->{MODEL_CID}",
            source=TOOL_CID, target=MODEL_CID,
            type=EdgeType.UNKNOWN_DEPENDENCY, label="unknown",
        ))
        nodes.append(GraphNode(id=TOOL_CID, type=NodeType.TOOL, label="Tool",
                               features={"component_identity_hash": TOOL_CID}))
    return CausalGraph(
        tenant_id=tenant_id,
        run_id=RUN_ID,
        nodes=nodes,
        edges=edges,
        trace_digest=hashlib.sha256(b"test-trace").hexdigest(),
    )


def _make_snapshot(
    tenant_id: UUID = TENANT_ID,
    extra_values: list[ExecutionStateValue] | None = None,
) -> ExecutionStateSnapshot:
    """Build a snapshot with standard pipeline variables."""
    values = [
        ExecutionStateValue(
            key="retriever_config",
            value_hash=hash_state_value({"top_k": 10, "version": "v2"}),
            variable_class=ExecutionVariableClass.FROZEN,
            source="retriever_config",
            timestamp=TS,
            component_id=RETRIEVER_CID,
        ),
        ExecutionStateValue(
            key="prompt_hash",
            value_hash=hash_state_value("You are a helpful assistant..."),
            variable_class=ExecutionVariableClass.FROZEN,
            source="prompt_hash",
            timestamp=TS,
            component_id=PROMPT_CID,
        ),
        ExecutionStateValue(
            key="model_version",
            value_hash=hash_state_value("gpt-4-0613"),
            variable_class=ExecutionVariableClass.FROZEN,
            source="model_version",
            timestamp=TS,
            component_id=MODEL_CID,
        ),
        ExecutionStateValue(
            key="random_seed",
            value_hash=hash_state_value(42),
            variable_class=ExecutionVariableClass.FROZEN,
            source="random_seed",
            timestamp=TS,
        ),
        ExecutionStateValue(
            key="policy_hash",
            value_hash=hash_state_value("policy-v1.0"),
            variable_class=ExecutionVariableClass.FROZEN,
            source="policy_hash",
            timestamp=TS,
            component_id=POLICY_CID,
        ),
        ExecutionStateValue(
            key="memory_snapshot_hash",
            value_hash=hash_state_value("memory-snapshot-001"),
            variable_class=ExecutionVariableClass.FROZEN,
            source="memory_snapshot_hash",
            timestamp=TS,
            component_id=MEMORY_CID,
        ),
    ]
    if extra_values:
        values.extend(extra_values)
    return ExecutionStateSnapshot(
        run_id=RUN_ID,
        trace_id=TRACE_ID,
        tenant_id=tenant_id,
        captured_at=TS,
        values=values,
    )


def _make_intervention(
    variable_key: str = "retriever_config",
    component_id: str = RETRIEVER_CID,
    intervention_type: CausalInterventionType = CausalInterventionType.CHANGE_RETRIEVER,
    snapshot: ExecutionStateSnapshot | None = None,
) -> CausalIntervention:
    """Build a single intervention on the specified variable."""
    if snapshot is None:
        snapshot = _make_snapshot()
    sv = snapshot.get_value(variable_key)
    assert sv is not None, f"Variable '{variable_key}' not in snapshot"
    replacement = hash_state_value("replacement-value-for-test")
    return CausalIntervention(
        component_id=component_id,
        variable_key=variable_key,
        original_value_hash=sv.value_hash,
        replacement_value_hash=replacement,
        intervention_type=intervention_type,
        reason="Test intervention",
    )


def _build_envelope(**kwargs) -> ReplayEquivalenceEnvelope:
    """Convenience: build envelope with default fixtures."""
    snapshot = kwargs.pop("snapshot", _make_snapshot())
    graph = kwargs.pop("graph", _make_graph())
    intervention = kwargs.pop("intervention", _make_intervention(snapshot=snapshot))
    builder = ReplayEquivalenceEnvelopeBuilder()
    defaults = dict(
        original_trace_id=TRACE_ID,
        causal_graph=graph,
        intervention=intervention,
        state_snapshot=snapshot,
        policy_version="v1.0",
        tenant_id=TENANT_ID,
    )
    defaults.update(kwargs)
    return builder.build(**defaults)


# ──────────────────────────────────────────────────────────────────────────────
# Contract Tests: CausalIntervention
# ──────────────────────────────────────────────────────────────────────────────

class TestCausalIntervention:
    def test_valid_construction(self):
        snapshot = _make_snapshot()
        intervention = _make_intervention(snapshot=snapshot)
        assert intervention.variable_key == "retriever_config"

    def test_noop_intervention_rejected(self):
        """original_value_hash == replacement_value_hash is a no-op."""
        h = hash_state_value("same-value")
        with pytest.raises(Exception, match="no-op"):
            CausalIntervention(
                component_id=RETRIEVER_CID,
                variable_key="retriever_config",
                original_value_hash=h,
                replacement_value_hash=h,
                intervention_type=CausalInterventionType.CHANGE_RETRIEVER,
                reason="Should fail",
            )

    def test_all_intervention_types(self):
        for it in CausalInterventionType:
            assert len(it.value) > 0


# ──────────────────────────────────────────────────────────────────────────────
# Builder Tests: Causal Descendant Computation
# ──────────────────────────────────────────────────────────────────────────────

class TestCausalDescendants:
    def test_retriever_intervention_descendants(self):
        """Intervening on Retriever → descendants are Reranker, Prompt, Model, Policy."""
        envelope = _build_envelope()
        # Retriever's causal descendants should include everything downstream
        assert RERANKER_CID in envelope.allowed_descendant_components
        assert PROMPT_CID in envelope.allowed_descendant_components
        assert MODEL_CID in envelope.allowed_descendant_components
        # Policy is downstream of Model via CONTROL_FLOW
        assert POLICY_CID in envelope.allowed_descendant_components
        # Memory is NOT downstream of Retriever
        assert MEMORY_CID not in envelope.allowed_descendant_components

    def test_prompt_intervention_descendants(self):
        """Intervening on Prompt → descendants are Model, Policy."""
        snapshot = _make_snapshot()
        intervention = _make_intervention(
            variable_key="prompt_hash",
            component_id=PROMPT_CID,
            intervention_type=CausalInterventionType.CHANGE_PROMPT,
            snapshot=snapshot,
        )
        envelope = _build_envelope(snapshot=snapshot, intervention=intervention)
        assert MODEL_CID in envelope.allowed_descendant_components
        assert POLICY_CID in envelope.allowed_descendant_components
        # Retriever is upstream of Prompt — NOT a descendant
        assert RETRIEVER_CID not in envelope.allowed_descendant_components
        assert RERANKER_CID not in envelope.allowed_descendant_components

    def test_model_version_change_descendants(self):
        """Intervening on Model → descendants are Policy only."""
        snapshot = _make_snapshot()
        intervention = _make_intervention(
            variable_key="model_version",
            component_id=MODEL_CID,
            intervention_type=CausalInterventionType.REPLACE_COMPONENT,
            snapshot=snapshot,
        )
        envelope = _build_envelope(snapshot=snapshot, intervention=intervention)
        assert POLICY_CID in envelope.allowed_descendant_components
        # Everything upstream of Model is NOT a descendant
        assert RETRIEVER_CID not in envelope.allowed_descendant_components
        assert PROMPT_CID not in envelope.allowed_descendant_components

    def test_memory_removal_descendants(self):
        """Intervening on Memory → Model is downstream via MEMORY_INFLUENCE."""
        snapshot = _make_snapshot()
        intervention = _make_intervention(
            variable_key="memory_snapshot_hash",
            component_id=MEMORY_CID,
            intervention_type=CausalInterventionType.REMOVE_MEMORY,
            snapshot=snapshot,
        )
        envelope = _build_envelope(snapshot=snapshot, intervention=intervention)
        assert MODEL_CID in envelope.allowed_descendant_components
        assert POLICY_CID in envelope.allowed_descendant_components
        # Retriever is not downstream of Memory
        assert RETRIEVER_CID not in envelope.allowed_descendant_components


# ──────────────────────────────────────────────────────────────────────────────
# Builder Tests: Variable Classification
# ──────────────────────────────────────────────────────────────────────────────

class TestVariableClassification:
    def test_frozen_variables_populated(self):
        """Variables not intervened and not downstream should be FROZEN."""
        envelope = _build_envelope()
        # When retriever is intervened, model_version is frozen because it's
        # not the intervention variable and is classified FROZEN in the snapshot
        assert "model_version" in envelope.frozen_variables
        assert "random_seed" in envelope.frozen_variables
        assert "policy_hash" in envelope.frozen_variables

    def test_intervened_variable_listed(self):
        """The intervention variable is in intervened_variables."""
        envelope = _build_envelope()
        assert "retriever_config" in envelope.intervened_variables

    def test_frozen_and_intervened_do_not_overlap(self):
        envelope = _build_envelope()
        frozen = set(envelope.frozen_variables)
        intervened = set(envelope.intervened_variables)
        assert len(frozen & intervened) == 0

    def test_exogenous_variable_handling(self):
        """Exogenous variables get a handling strategy."""
        extra = [ExecutionStateValue(
            key="external_api_result",
            value_hash=hash_state_value("external-response-42"),
            variable_class=ExecutionVariableClass.EXOGENOUS,
            source="external_api_response_hash",
            timestamp=TS,
        )]
        snapshot = _make_snapshot(extra_values=extra)
        intervention = _make_intervention(snapshot=snapshot)
        envelope = _build_envelope(snapshot=snapshot, intervention=intervention)
        exo_keys = [ev.variable_key for ev in envelope.exogenous_variables]
        assert "external_api_result" in exo_keys
        exo = next(ev for ev in envelope.exogenous_variables
                   if ev.variable_key == "external_api_result")
        assert exo.strategy == ExogenousHandlingStrategy.FREEZE_RECORDED_VALUE

    def test_nondeterministic_variable(self):
        """Nondeterministic variables are tracked."""
        extra = [ExecutionStateValue(
            key="sampling_output",
            value_hash=hash_state_value("random-output"),
            variable_class=ExecutionVariableClass.NONDETERMINISTIC,
            source="custom",
            timestamp=TS,
        )]
        snapshot = _make_snapshot(extra_values=extra)
        intervention = _make_intervention(snapshot=snapshot)
        envelope = _build_envelope(snapshot=snapshot, intervention=intervention)
        assert "sampling_output" in envelope.nondeterministic_variables


# ──────────────────────────────────────────────────────────────────────────────
# Builder Tests: Validation Errors
# ──────────────────────────────────────────────────────────────────────────────

class TestEnvelopeValidationErrors:
    def test_missing_graph_node_rejected(self):
        """Intervention on a component not in the graph → error."""
        snapshot = _make_snapshot()
        intervention = CausalIntervention(
            component_id="nonexistent-component-id",
            variable_key="retriever_config",
            original_value_hash=snapshot.get_value("retriever_config").value_hash,
            replacement_value_hash=hash_state_value("new"),
            intervention_type=CausalInterventionType.CHANGE_RETRIEVER,
            reason="Should fail",
        )
        with pytest.raises(EnvelopeValidationError, match="does not exist"):
            _build_envelope(snapshot=snapshot, intervention=intervention)

    def test_cross_tenant_graph_rejected(self):
        """Graph with different tenant → error."""
        other_tenant = uuid4()
        graph = _make_graph(tenant_id=other_tenant)
        with pytest.raises(EnvelopeValidationError, match="Cross-tenant graph"):
            _build_envelope(graph=graph)

    def test_cross_tenant_snapshot_rejected(self):
        """Snapshot with different tenant → error."""
        other_tenant = uuid4()
        snapshot = _make_snapshot(tenant_id=other_tenant)
        intervention = _make_intervention(snapshot=snapshot)
        with pytest.raises(EnvelopeValidationError, match="Cross-tenant state snapshot"):
            _build_envelope(snapshot=snapshot, intervention=intervention)

    def test_multiple_intervention_rejected(self):
        """Two INTERVENED variables in the snapshot → error."""
        extra = [ExecutionStateValue(
            key="second_intervention",
            value_hash=hash_state_value("v2"),
            variable_class=ExecutionVariableClass.INTERVENED,
            source="custom",
            timestamp=TS,
        )]
        snapshot = _make_snapshot(extra_values=extra)
        intervention = _make_intervention(snapshot=snapshot)
        with pytest.raises(EnvelopeValidationError, match="Multiple INTERVENED"):
            _build_envelope(snapshot=snapshot, intervention=intervention)

    def test_unknown_classification_strict_rejected(self):
        """UNKNOWN variables in strict mode → error."""
        extra = [ExecutionStateValue(
            key="mystery_variable",
            value_hash=hash_state_value("mystery"),
            variable_class=ExecutionVariableClass.UNKNOWN,
            source="custom",
            timestamp=TS,
        )]
        snapshot = _make_snapshot(extra_values=extra)
        intervention = _make_intervention(snapshot=snapshot)
        with pytest.raises(EnvelopeValidationError, match="UNKNOWN classification"):
            _build_envelope(snapshot=snapshot, intervention=intervention, strict_mode=True)

    def test_unknown_classification_non_strict_allowed(self):
        """UNKNOWN variables in non-strict mode → classified as nondeterministic."""
        extra = [ExecutionStateValue(
            key="mystery_variable",
            value_hash=hash_state_value("mystery"),
            variable_class=ExecutionVariableClass.UNKNOWN,
            source="custom",
            timestamp=TS,
        )]
        snapshot = _make_snapshot(extra_values=extra)
        intervention = _make_intervention(snapshot=snapshot)
        envelope = _build_envelope(
            snapshot=snapshot, intervention=intervention, strict_mode=False
        )
        assert "mystery_variable" in envelope.nondeterministic_variables

    def test_unknown_dependency_edge_strict_rejected(self):
        """Graph with UNKNOWN_DEPENDENCY edge in strict mode → error."""
        graph = _make_graph(include_unknown_edge=True)
        with pytest.raises(EnvelopeValidationError, match="UNKNOWN_DEPENDENCY"):
            _build_envelope(graph=graph)

    def test_intervention_variable_not_in_snapshot_rejected(self):
        """Intervening on a variable key not in the snapshot → error."""
        snapshot = _make_snapshot()
        intervention = CausalIntervention(
            component_id=RETRIEVER_CID,
            variable_key="nonexistent_variable",
            original_value_hash=hash_state_value("a"),
            replacement_value_hash=hash_state_value("b"),
            intervention_type=CausalInterventionType.CHANGE_RETRIEVER,
            reason="Should fail",
        )
        with pytest.raises(EnvelopeValidationError, match="not found"):
            _build_envelope(snapshot=snapshot, intervention=intervention)

    def test_intervention_hash_mismatch_rejected(self):
        """original_value_hash does not match snapshot → error."""
        snapshot = _make_snapshot()
        intervention = CausalIntervention(
            component_id=RETRIEVER_CID,
            variable_key="retriever_config",
            original_value_hash=hash_state_value("wrong-value"),
            replacement_value_hash=hash_state_value("new"),
            intervention_type=CausalInterventionType.CHANGE_RETRIEVER,
            reason="Should fail",
        )
        with pytest.raises(EnvelopeValidationError, match="does not match snapshot"):
            _build_envelope(snapshot=snapshot, intervention=intervention)


# ──────────────────────────────────────────────────────────────────────────────
# Envelope Contract Tests: Structural Validation
# ──────────────────────────────────────────────────────────────────────────────

class TestEnvelopeContractValidation:
    def test_frozen_intervened_overlap_rejected(self):
        """Cannot have the same key in both frozen_variables and intervened_variables."""
        snapshot = _make_snapshot()
        intervention = _make_intervention(snapshot=snapshot)
        with pytest.raises(Exception, match="overlap"):
            ReplayEquivalenceEnvelope(
                original_trace_id=TRACE_ID,
                replay_id=uuid4(),
                tenant_id=TENANT_ID,
                intervention=intervention,
                original_state_hash=snapshot.snapshot_hash,
                frozen_variables=["retriever_config"],
                intervened_variables=["retriever_config"],
                policy_version="v1.0",
            )

    def test_allowed_forbidden_overlap_rejected(self):
        """Cannot have the same component in both allowed and forbidden."""
        snapshot = _make_snapshot()
        intervention = _make_intervention(snapshot=snapshot)
        with pytest.raises(Exception, match="overlap"):
            ReplayEquivalenceEnvelope(
                original_trace_id=TRACE_ID,
                replay_id=uuid4(),
                tenant_id=TENANT_ID,
                intervention=intervention,
                original_state_hash=snapshot.snapshot_hash,
                allowed_descendant_components=[RERANKER_CID],
                forbidden_divergence_components=[RERANKER_CID],
                policy_version="v1.0",
            )

    def test_frozen_nondeterministic_overlap_rejected(self):
        """Cannot be both FROZEN and NONDETERMINISTIC."""
        snapshot = _make_snapshot()
        intervention = _make_intervention(snapshot=snapshot)
        with pytest.raises(Exception, match="FROZEN and NONDETERMINISTIC"):
            ReplayEquivalenceEnvelope(
                original_trace_id=TRACE_ID,
                replay_id=uuid4(),
                tenant_id=TENANT_ID,
                intervention=intervention,
                original_state_hash=snapshot.snapshot_hash,
                frozen_variables=["random_seed"],
                nondeterministic_variables=["random_seed"],
                policy_version="v1.0",
            )


# ──────────────────────────────────────────────────────────────────────────────
# Envelope Cryptographic Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestEnvelopeCryptography:
    def test_hash_is_64_hex(self):
        envelope = _build_envelope()
        assert len(envelope.envelope_hash) == 64
        int(envelope.envelope_hash, 16)

    def test_hash_deterministic(self):
        """Same inputs → same hash."""
        snapshot = _make_snapshot()
        intervention = _make_intervention(snapshot=snapshot)
        replay_id = uuid4()
        builder = ReplayEquivalenceEnvelopeBuilder()
        
        e1 = builder.build(
            original_trace_id=TRACE_ID, causal_graph=_make_graph(),
            intervention=intervention, state_snapshot=snapshot,
            policy_version="v1.0", tenant_id=TENANT_ID, replay_id=replay_id,
        )
        e2 = builder.build(
            original_trace_id=TRACE_ID, causal_graph=_make_graph(),
            intervention=intervention, state_snapshot=snapshot,
            policy_version="v1.0", tenant_id=TENANT_ID, replay_id=replay_id,
        )
        
        # Override auto-generated fields so e2 exactly matches e1 structurally
        e2.envelope_id = e1.envelope_id
        e2.generated_at = e1.generated_at
        e2.intervention.intervention_id = e1.intervention.intervention_id
        e2.envelope_hash = e2._compute_hash()
        
        assert e1.envelope_hash == e2.envelope_hash

    def test_verify_integrity_passes(self):
        envelope = _build_envelope()
        assert envelope.verify_integrity() is True

    def test_tampered_envelope_detected(self):
        """Modifying a field after construction breaks integrity."""
        envelope = _build_envelope()
        # Tamper with policy_version
        object.__setattr__(envelope, "policy_version", "v2.0-tampered")
        assert envelope.verify_integrity() is False

    def test_tampered_frozen_list_detected(self):
        """Adding a key to frozen_variables breaks integrity."""
        envelope = _build_envelope()
        envelope.frozen_variables.append("injected_key")
        assert envelope.verify_integrity() is False

    def test_different_policy_different_hash(self):
        """Different policy version → different hash."""
        snapshot = _make_snapshot()
        intervention = _make_intervention(snapshot=snapshot)
        replay_id = uuid4()
        builder = ReplayEquivalenceEnvelopeBuilder()
        e1 = builder.build(
            original_trace_id=TRACE_ID, causal_graph=_make_graph(),
            intervention=intervention, state_snapshot=snapshot,
            policy_version="v1.0", tenant_id=TENANT_ID, replay_id=replay_id,
        )
        e2 = builder.build(
            original_trace_id=TRACE_ID, causal_graph=_make_graph(),
            intervention=intervention, state_snapshot=snapshot,
            policy_version="v2.0", tenant_id=TENANT_ID, replay_id=replay_id,
        )
        assert e1.envelope_hash != e2.envelope_hash


# ──────────────────────────────────────────────────────────────────────────────
# Equivalence Constraints Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestEquivalenceConstraints:
    def test_security_fields_get_exact_hash(self):
        """Security-critical fields default to EXACT_HASH."""
        envelope = _build_envelope()
        constraint_map = {c.variable_key: c for c in envelope.equivalence_constraints}
        # random_seed and policy_hash are security-critical
        assert constraint_map["random_seed"].constraint_type == \
               EquivalenceConstraintType.EXACT_HASH
        assert constraint_map["policy_hash"].constraint_type == \
               EquivalenceConstraintType.EXACT_HASH

    def test_version_fields_get_exact_version(self):
        """Fields with 'version' in the name default to EXACT_VERSION."""
        envelope = _build_envelope()
        constraint_map = {c.variable_key: c for c in envelope.equivalence_constraints}
        assert constraint_map["model_version"].constraint_type == \
               EquivalenceConstraintType.EXACT_VERSION

    def test_all_frozen_have_constraints(self):
        """Every frozen variable must have a corresponding constraint."""
        envelope = _build_envelope()
        constrained_keys = {c.variable_key for c in envelope.equivalence_constraints}
        for fk in envelope.frozen_variables:
            assert fk in constrained_keys, f"Frozen key '{fk}' has no constraint"

    def test_constraint_types_are_valid(self):
        """All constraint types in the enum."""
        for ct in EquivalenceConstraintType:
            assert len(ct.value) > 0


# ──────────────────────────────────────────────────────────────────────────────
# RAEB Envelope-Aware Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestRAEBEnvelopeAware:
    def _make_trace_and_replay(self):
        from packages.contracts.src.models import (
            TraceArtifact,
            SpanRecord,
            SpanKind,
            ReplayEpisode,
            ReplayStatus,
        )
        trace = TraceArtifact(
            run_id=RUN_ID,
            tenant_id=TENANT_ID,
            pipeline_id=uuid4(),
            created_at=TS,
            spans=[
                SpanRecord(
                    trace_id="a" * 32,
                    span_id="b" * 16,
                    name="root",
                    kind=SpanKind.INTERNAL,
                    start_time=TS,
                    end_time=TS + timedelta(seconds=1),
                    tenant_id=TENANT_ID,
                    pipeline_id=uuid4(),
                    run_id=RUN_ID,
                )
            ],
        )
        replay = ReplayEpisode(
            tenant_id=TENANT_ID,
            run_id=RUN_ID,
            swapped_component_type=ComponentType.RETRIEVER,
            original_version_id=uuid4(),
            replay_version_id=uuid4(),
            original_version_tag="v2-exp",
            replay_version_tag="v1",
            status=ReplayStatus.COMPLETED,
        )
        return trace, replay

    def test_tampered_envelope_rejected_by_raeb(self):
        """RAEB rejects tampered envelope."""
        from packages.replay.src.raeb import RAEBGateway
        trace, replay = self._make_trace_and_replay()
        envelope = _build_envelope()
        # Tamper
        object.__setattr__(envelope, "policy_version", "TAMPERED")
        gateway = RAEBGateway(freshness_ttl_seconds=7200)
        result = gateway.evaluate_with_envelope(
            trace, replay, envelope,
            current_time=TS + timedelta(seconds=10),
        )
        assert result.admissibility == "unsupported"
        assert "integrity" in result.rejection_reason.lower()

    def test_cross_tenant_envelope_rejected_by_raeb(self):
        """RAEB rejects envelope with different tenant than trace."""
        from packages.replay.src.raeb import RAEBGateway
        trace, replay = self._make_trace_and_replay()
        # Build envelope with a different tenant
        other_tenant = uuid4()
        snapshot = _make_snapshot(tenant_id=other_tenant)
        graph = _make_graph(tenant_id=other_tenant)
        intervention = _make_intervention(snapshot=snapshot)
        envelope = ReplayEquivalenceEnvelopeBuilder().build(
            original_trace_id=TRACE_ID,
            causal_graph=graph,
            intervention=intervention,
            state_snapshot=snapshot,
            policy_version="v1.0",
            tenant_id=other_tenant,
        )
        gateway = RAEBGateway(freshness_ttl_seconds=7200)
        result = gateway.evaluate_with_envelope(
            trace, replay, envelope,
            current_time=TS + timedelta(seconds=10),
        )
        assert result.admissibility == "unsupported"
        assert "tenant" in result.rejection_reason.lower()

    def test_valid_envelope_admissible(self):
        """Valid envelope with fresh trace → ADMISSIBLE."""
        from packages.replay.src.raeb import RAEBGateway
        trace, replay = self._make_trace_and_replay()
        envelope = _build_envelope()
        gateway = RAEBGateway(freshness_ttl_seconds=7200)
        result = gateway.evaluate_with_envelope(
            trace, replay, envelope,
            current_time=TS + timedelta(seconds=10),
        )
        assert result.admissibility in ("admissible", "limited")


# ──────────────────────────────────────────────────────────────────────────────
# Exogenous Handling Strategy Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestExogenousStrategies:
    def test_all_strategies_defined(self):
        expected = {
            "FREEZE_RECORDED_VALUE",
            "REPLAY_FROM_SNAPSHOT",
            "REQUERY_AND_MARK_REGIME_CHANGE",
            "MOCK_FROM_CAPTURE",
            "UNCONTROLLABLE",
            "REJECT_REPLAY",
        }
        actual = {s.name for s in ExogenousHandlingStrategy}
        assert expected == actual

    def test_reject_replay_blocks_envelope(self):
        """An exogenous variable requiring REJECT_REPLAY blocks envelope creation."""
        extra = [ExecutionStateValue(
            key="critical_api_result",
            value_hash=hash_state_value(None),  # Valid hash
            variable_class=ExecutionVariableClass.EXOGENOUS,
            source="external_api_response_hash",
            timestamp=TS,
            metadata={"capture_failed": True},
        )]
        snapshot = _make_snapshot(extra_values=extra)
        intervention = _make_intervention(snapshot=snapshot)
        with pytest.raises(EnvelopeValidationError, match="REJECT_REPLAY"):
            _build_envelope(snapshot=snapshot, intervention=intervention, strict_mode=True)
