"""
Unit tests: Dynamic Causal Divergence Validator.
Tests frozen-state detection, forbidden divergence early termination,
causal reachability, and tolerance rules.
"""
import os

os.environ.setdefault("DGX_CAPABILITY_SECRET", "test-secret-key")

from packages.contracts.src.recovery_models import (
    CausalRecoveryCut,
    FailureTarget,
    FaultSource,
    OptimizationMethod,
    ReplayEquivalenceEnvelope,
)
from packages.replay.src.divergence_validator import (
    DynamicCausalDivergenceValidator,
    ExecutionSnapshot,
    NodeState,
    _stable_hash,
)


def _make_envelope(**kwargs) -> ReplayEquivalenceEnvelope:
    cut = CausalRecoveryCut(
        fault_sources=[FaultSource(node_id="retriever", probability=1.0)],
        failure_targets=[FailureTarget(node_id="output", failure_type="test", severity="low")],
        selected_actions=[],
        optimization_method=OptimizationMethod.EXACT,
        evidence_hash="test",
    )
    return ReplayEquivalenceEnvelope(trace_id="t", recovery_cut=cut, invariants=[], **kwargs)


def _snap(outputs: dict) -> ExecutionSnapshot:
    return ExecutionSnapshot(
        nodes={k: NodeState(node_id=k, output=v) for k, v in outputs.items()}
    )


class TestDivergenceValidator:
    def setup_method(self):
        self.validator = DynamicCausalDivergenceValidator()

    def test_identical_snapshots_are_valid(self):
        orig = _snap({"a": "val_a", "b": "val_b"})
        replay = _snap({"a": "val_a", "b": "val_b"})
        env = _make_envelope()
        report = self.validator.validate(orig, replay, env)
        assert report.valid

    def test_intervened_node_change_is_expected(self):
        orig = _snap({"retriever": "old_output", "generator": "same"})
        replay = _snap({"retriever": "new_output", "generator": "same"})
        env = _make_envelope(intervened_variables=["retriever"])
        report = self.validator.validate(orig, replay, env)
        assert report.valid, f"Intervened node change should be valid: {report.reason}"

    def test_frozen_variable_violation_detected(self):
        orig = _snap({"policy_gate": "expected_val"})
        replay = _snap({"policy_gate": "TAMPERED_val"})
        env = _make_envelope(
            frozen_variables={"policy_gate": _stable_hash("expected_val")}
        )
        report = self.validator.validate(orig, replay, env)
        assert not report.valid
        assert "policy_gate" in report.violated_frozen_nodes

    def test_forbidden_divergence_triggers_early_termination(self):
        orig = _snap({"auth_gate": "pass", "generator": "output"})
        replay = _snap({"auth_gate": "fail", "generator": "output"})
        env = _make_envelope(forbidden_divergence_nodes=["auth_gate"])
        report = self.validator.validate(orig, replay, env)
        assert not report.valid
        assert report.early_terminated
        assert "auth_gate" in report.violated_forbidden_nodes

    def test_allowed_descendant_change_passes(self):
        # retriever is the intervened node (change expected, skipped by validator)
        # generator is an allowed descendant — its change IS permitted
        orig = _snap({"retriever": "old_ret", "generator": "old_gen", "cache": "same"})
        replay = _snap({"retriever": "new_ret", "generator": "new_gen", "cache": "same"})
        env = _make_envelope(
            intervened_variables=["retriever"],
            allowed_causal_descendants=["generator"],
            # cache is not allowed to change — it stays the same in replay, so no violation
        )
        report = self.validator.validate(orig, replay, env)
        assert report.valid, f"Allowed descendant + intervened node changes should be valid: {report.reason} | {report.per_node}"

    def test_unexpected_non_descendant_change_fails(self):
        orig = _snap({"retriever": "old", "unrelated_cache": "cached_val"})
        replay = _snap({"retriever": "new", "unrelated_cache": "DIFFERENT"})
        env = _make_envelope(
            intervened_variables=["retriever"],
            allowed_causal_descendants=["generator"],  # unrelated_cache is NOT listed
        )
        report = self.validator.validate(orig, replay, env)
        assert not report.valid

    def test_numeric_tolerance_passes_within_threshold(self):
        orig = _snap({"score": 0.85})
        replay = _snap({"score": 0.87})
        env = _make_envelope(
            constraints={"score": {"type": "numeric_delta", "threshold": 0.05}}
        )
        report = self.validator.validate(orig, replay, env)
        assert report.valid, f"Within tolerance should pass: {report.reason}"

    def test_numeric_tolerance_fails_outside_threshold(self):
        orig = _snap({"score": 0.85})
        replay = _snap({"score": 0.50})
        env = _make_envelope(
            constraints={"score": {"type": "numeric_delta", "threshold": 0.05}}
        )
        report = self.validator.validate(orig, replay, env)
        assert not report.valid

    def test_validate_divergence_adapter(self):
        replays = [{"original_spans": [], "replay_spans": []}]
        env = _make_envelope()
        report = self.validator.validate_divergence(replays, env)
        assert report.valid

    def test_bool_conversion(self):
        from packages.contracts.src.interfaces import DivergenceReport
        assert DivergenceReport(valid=True)
        assert not DivergenceReport(valid=False)
