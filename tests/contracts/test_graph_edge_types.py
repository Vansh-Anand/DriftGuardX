"""
Tests for graph EdgeType extension and CausalRecoveryConfig

Covers:
- New EdgeType values exist without breaking old values
- EdgeType string values unchanged (backward compat)
- CausalRecoveryConfig dependency ordering
- CausalRecoveryConfig defaults
- Schema validation
"""
from __future__ import annotations

import pytest

from packages.contracts.src.graph import EdgeType
from packages.contracts.src.config import CausalRecoveryConfig


# ─── EdgeType Backward Compatibility ─────────────────────────────────────────

class TestEdgeTypeBackwardCompat:
    """Existing EdgeType string values must remain identical."""

    def test_original_values_unchanged(self):
        assert EdgeType.DATA_DEPENDENCY.value == "data_dependency"
        assert EdgeType.CONTROL_FLOW.value == "control_flow"
        assert EdgeType.VERSION_LINEAGE.value == "version_lineage"
        assert EdgeType.POLICY_DEPENDENCY.value == "policy_dependency"
        assert EdgeType.MEMORY_INFLUENCE.value == "memory_influence"
        assert EdgeType.EVIDENCE_CITATION.value == "evidence_citation"
        assert EdgeType.TOOL_EFFECT.value == "tool_effect"
        assert EdgeType.RETRY_FALLBACK.value == "retry_fallback"
        assert EdgeType.INTER_AGENT_COMMUNICATION.value == "inter_agent_communication"

    def test_new_causal_edges_exist(self):
        assert EdgeType.CONTROL_DEPENDENCY.value == "control_dependency"
        assert EdgeType.MEMORY_DEPENDENCY.value == "memory_dependency"
        assert EdgeType.TOOL_DEPENDENCY.value == "tool_dependency"
        assert EdgeType.DERIVED_DEPENDENCY.value == "derived_dependency"
        assert EdgeType.UNKNOWN_DEPENDENCY.value == "unknown_dependency"

    def test_control_flow_is_not_control_dependency(self):
        """Critical: temporal ordering must not be conflated with causal dependency."""
        assert EdgeType.CONTROL_FLOW != EdgeType.CONTROL_DEPENDENCY


# ─── CausalRecoveryConfig ─────────────────────────────────────────────────────

class TestCausalRecoveryConfig:
    def test_safe_defaults(self):
        cfg = CausalRecoveryConfig.safe_defaults()
        assert cfg.replay_equivalence_enabled is False
        assert cfg.divergence_frontier_enabled is False
        assert cfg.sequential_planner_enabled is False
        assert cfg.recovery_cut_enabled is False
        assert cfg.transportability_enabled is False
        assert cfg.strict_mode is True

    def test_full_pipeline(self):
        cfg = CausalRecoveryConfig.full_pipeline()
        assert cfg.replay_equivalence_enabled is True
        assert cfg.divergence_frontier_enabled is True
        assert cfg.recovery_cut_enabled is True
        assert cfg.transportability_enabled is True
        assert cfg.strict_mode is True

    def test_divergence_requires_replay_equivalence(self):
        with pytest.raises(Exception, match="divergence_frontier_enabled requires"):
            CausalRecoveryConfig(
                replay_equivalence_enabled=False,
                divergence_frontier_enabled=True,
            )

    def test_transportability_requires_recovery_cut(self):
        with pytest.raises(Exception, match="transportability_enabled requires"):
            CausalRecoveryConfig(
                recovery_cut_enabled=False,
                transportability_enabled=True,
            )

    def test_sequential_planner_alone_is_valid(self):
        cfg = CausalRecoveryConfig(sequential_planner_enabled=True)
        assert cfg.sequential_planner_enabled is True

    def test_schema_version_present(self):
        cfg = CausalRecoveryConfig()
        assert cfg.schema_version == "1.0"

    def test_explicit_construction(self):
        cfg = CausalRecoveryConfig(
            replay_equivalence_enabled=True,
            divergence_frontier_enabled=True,
        )
        assert cfg.replay_equivalence_enabled is True
        assert cfg.divergence_frontier_enabled is True
