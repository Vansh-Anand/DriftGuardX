import os
from datetime import UTC, datetime, timedelta

from packages.contracts.src.recovery_models import (
    CausalRecoveryCut,
    FailureTarget,
    FaultSource,
    OptimizationMethod,
    RecoveryAction,
    RecoveryInvariant,
    ReplayContext,
    ReplayEquivalenceEnvelope,
    SandboxOutcome,
)
from packages.memory.src.auth import AccessContext
from packages.recovery.src.replay_executor import (
    LocalPipelineRecoveryReplayExecutor,
    SyntheticRecoveryReplayExecutor,
)
from packages.recovery.src.validation import RecoveryValidator

# Set required environment variables for tests
os.environ["DGX_CAPABILITY_SECRET"] = "test_secret_for_testing"


# --- Mock Pipeline ---
class MockPipeline:
    def __init__(self):
        self.components = {"A": "faulty", "B": "good"}
        self.patched = False
        self.trace_id = "0" * 32

    def apply_patch(self, component: str, replacement: str):
        if component in self.components:
            self.components[component] = replacement
            self.patched = True

    def execute(self, config: dict):
        # Fresh trace generation
        spans = [
            {
                "span_id": "a1",
                "component_type": "A",
                "output": {"status": "recovered" if self.components["A"] == "fixed" else "failed"},
            },
            {"span_id": "b1", "component_type": "B", "output": {"status": "success"}},
        ]
        failure_status = "resolved" if self.components["A"] == "fixed" else "failed"
        return {
            "spans": spans,
            "metrics": {"regression_count": 0.0, "blast_radius": 0.1},
            "state_snapshot": {"A": self.components["A"]},
            "failure_status": failure_status,
        }


def _create_mock_cut(
    action_type: str, component: str = "A", replacement: str | None = None
) -> CausalRecoveryCut:
    action = RecoveryAction(
        target_component=component,
        action_type=action_type,
        replacement=replacement,
        regression_risk=0.0,
        blast_radius=0.1,
    )
    return CausalRecoveryCut(
        fault_sources=[FaultSource(node_id=component, probability=1.0)],
        failure_targets=[
            FailureTarget(node_id="b1", failure_type="downstream_error", severity="high")
        ],
        selected_actions=[action],
        optimization_method=OptimizationMethod.EXACT,
        evidence_hash="hash",
    )


def _create_mock_envelope(cut: CausalRecoveryCut) -> ReplayEquivalenceEnvelope:
    return ReplayEquivalenceEnvelope(
        trace_id="0" * 32,
        recovery_cut=cut,
        invariants=[],
        exogenous_variables={},
    )


def _mock_sandbox_run(func, inputs, timeout_seconds, trace_id):
    return func(**inputs)


def test_1_real_local_test_pipeline():
    from unittest.mock import patch

    # 1. Real local test pipeline: Inject real fault, recovery changes A, fresh output shows recovery
    cut = _create_mock_cut("REPLACE", "A", "fixed")
    env = _create_mock_envelope(cut)
    ctx = ReplayContext(original_trace_id="0" * 32, original_spans=[])

    executor = LocalPipelineRecoveryReplayExecutor(pipeline_factory=MockPipeline)
    with patch(
        "packages.recovery.src.replay_executor.SandboxedWorker.run", side_effect=_mock_sandbox_run
    ):
        result = executor.replay(None, cut, env, ctx)

    assert result.outcome == SandboxOutcome.SUCCESS
    assert result.target_failure_status == "resolved"
    assert len(result.new_spans) == 2
    assert result.new_spans[0]["output"]["status"] == "recovered"


def test_2_wrong_recovery_action():
    from unittest.mock import patch

    # 2. Wrong recovery action: failure remains. failure_resolved=False
    cut = _create_mock_cut("REPLACE", "A", "wrong_fix")
    env = _create_mock_envelope(cut)
    ctx = ReplayContext(original_trace_id="0" * 32, original_spans=[])

    executor = LocalPipelineRecoveryReplayExecutor(pipeline_factory=MockPipeline)
    with patch(
        "packages.recovery.src.replay_executor.SandboxedWorker.run", side_effect=_mock_sandbox_run
    ):
        result = executor.replay(None, cut, env, ctx)

    assert result.outcome == SandboxOutcome.SUCCESS
    assert result.target_failure_status == "failed"
    assert result.new_spans[0]["output"]["status"] == "failed"


def test_3_invariant_regression():
    # 3. Invariant regression: target fixed but invariant breaks -> eligible_for_canary=False
    cut = _create_mock_cut("REPLACE", "A", "fixed")
    inv = RecoveryInvariant(
        scope="system",
        metric="blast_radius",
        baseline=0.0,
        allowed_deviation=0.05,
        severity="high",
        evidence_source="test",
    )
    ReplayEquivalenceEnvelope(
        trace_id="0" * 32, recovery_cut=cut, invariants=[inv], exogenous_variables={}
    )
    ReplayContext(original_trace_id="0" * 32, original_spans=[])

    # Needs the orchestrator / validator to run
    validator = RecoveryValidator(
        executor=LocalPipelineRecoveryReplayExecutor(pipeline_factory=MockPipeline)
    )

    # Mock capability check by not requiring any for this test
    # (By default cut.selected_actions have required_capability=None, so it passes)

    class MockDivergenceReport:
        valid = True
        reason = ""
        violated_frozen_nodes = []
        violated_forbidden_nodes = []
        per_node = {}

    class MockDivergenceValidator:
        def validate_divergence(self, *args, **kwargs):
            return MockDivergenceReport()

    validator.divergence_validator = MockDivergenceValidator()

    from unittest.mock import patch

    access = AccessContext(
        requester_id="test",
        tenant_id="test",
        capabilities=[],
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    # The pipeline will return blast_radius = 0.1, which exceeds baseline(0.0) + allowed(0.05)
    with patch(
        "packages.recovery.src.replay_executor.SandboxedWorker.run", side_effect=_mock_sandbox_run
    ):
        res = validator.validate_cut(
            cut, invariants=[inv], trace_id="0" * 32, original_spans=[], access_context=access
        )

    assert res.eligible_for_canary is False
    assert res.invariants_satisfied is False
    assert "blast_radius" in str(res.divergence_report)


def test_4_sandbox_unavailable_production():
    # 4. Sandbox unavailable in production: fail closed.
    cut = _create_mock_cut("REPLACE", "A", "fixed")
    inv = []

    validator = RecoveryValidator(executor=SyntheticRecoveryReplayExecutor())

    access = AccessContext(
        requester_id="test",
        tenant_id="test",
        capabilities=[],
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )

    # Mock production mode
    os.environ["DGX_MODE"] = "production"
    try:
        res = validator.validate_cut(
            cut, invariants=inv, trace_id="0" * 32, original_spans=[], access_context=access
        )
        assert res.eligible_for_canary is False
        assert "Synthetic execution is forbidden in production" in str(res.divergence_report)
    finally:
        del os.environ["DGX_MODE"]


def test_5_synthetic_executor_only_requested():
    # 5. Synthetic executor explicitly requested, simulated=True in metadata
    cut = _create_mock_cut("REPLACE", "A", "fixed")
    env = _create_mock_envelope(cut)
    ctx = ReplayContext(
        original_trace_id="0" * 32,
        original_spans=[{"component_type": "A", "output": {"status": "failed"}}],
    )

    executor = SyntheticRecoveryReplayExecutor()
    result = executor.replay(None, cut, env, ctx)

    assert result.executor_metadata.get("simulated") is True
    assert result.outcome == SandboxOutcome.SUCCESS
    assert result.new_spans[0]["output"]["status"] == "recovered"


def test_6_replay_trace_freshly_generated():
    from unittest.mock import patch

    # 6. Replay trace freshly generated
    cut = _create_mock_cut("REPLACE", "A", "fixed")
    env = _create_mock_envelope(cut)
    original_spans = [{"span_id": "old", "component_type": "A", "output": {"status": "failed"}}]
    ctx = ReplayContext(original_trace_id="0" * 32, original_spans=original_spans)

    executor = LocalPipelineRecoveryReplayExecutor(pipeline_factory=MockPipeline)
    with patch(
        "packages.recovery.src.replay_executor.SandboxedWorker.run", side_effect=_mock_sandbox_run
    ):
        result = executor.replay(None, cut, env, ctx)

    assert len(result.new_spans) == 2
    assert result.new_spans[0]["span_id"] == "a1"
    assert result.new_spans[0] not in original_spans  # entirely fresh


def test_7_unsupported_action_rejected():
    from unittest.mock import patch

    # 7. Unsupported action rejected
    cut = _create_mock_cut("MAGIC_FIX", "A", "fixed")
    env = _create_mock_envelope(cut)
    ctx = ReplayContext(original_trace_id="0" * 32, original_spans=[])

    executor = LocalPipelineRecoveryReplayExecutor(pipeline_factory=MockPipeline)
    with patch(
        "packages.recovery.src.replay_executor.SandboxedWorker.run", side_effect=_mock_sandbox_run
    ):
        result = executor.replay(None, cut, env, ctx)

    assert result.outcome == SandboxOutcome.ACTION_UNSUPPORTED
    assert result.executor_metadata["error_details"]["_error"] == "ACTION_UNSUPPORTED"


def test_8_exogenous_failure_rejects():
    # 8. Exogenous controller failure rejects validation
    cut = _create_mock_cut("REPLACE", "A", "fixed")
    env = _create_mock_envelope(cut)
    # Exogenous variables missing or badly formatted can trigger controller failure, but let's mock it
    ctx = ReplayContext(original_trace_id="0" * 32, original_spans=[])

    class FailingPipeline:
        def apply_patch(self, component, replacement):
            pass

        def execute(self, config):
            raise RuntimeError("Exogenous failure")

    executor = LocalPipelineRecoveryReplayExecutor(pipeline_factory=FailingPipeline)
    from unittest.mock import patch

    with patch(
        "packages.recovery.src.replay_executor.SandboxedWorker.run", side_effect=_mock_sandbox_run
    ):
        result = executor.replay(None, cut, env, ctx)

    assert result.outcome == SandboxOutcome.REPLAY_EXECUTION_FAILURE
    assert "Exogenous failure" in result.executor_metadata.get("error_details", {}).get(
        "details", ""
    )


def test_9_divergence_rejects_validation():
    # 9. Divergence outside REE rejects validation
    cut = _create_mock_cut("REPLACE", "A", "fixed")
    inv = []

    validator = RecoveryValidator(
        executor=LocalPipelineRecoveryReplayExecutor(pipeline_factory=MockPipeline)
    )

    class FailingDivergenceReport:
        valid = False
        reason = "Frozen node B diverged"
        violated_frozen_nodes = ["B"]
        violated_forbidden_nodes = []
        per_node = {}

    class FailingDivergenceValidator:
        def validate_divergence(self, *args, **kwargs):
            return FailingDivergenceReport()

    validator.divergence_validator = FailingDivergenceValidator()

    from unittest.mock import patch

    access = AccessContext(
        requester_id="test",
        tenant_id="test",
        capabilities=[],
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    with patch(
        "packages.recovery.src.replay_executor.SandboxedWorker.run", side_effect=_mock_sandbox_run
    ):
        res = validator.validate_cut(
            cut, invariants=inv, trace_id="0" * 32, original_spans=[], access_context=access
        )

    assert res.eligible_for_canary is False
    assert "Frozen node B diverged" in str(res.divergence_report)


def test_10_recovery_certificate_metadata():
    from unittest.mock import patch

    # 10. recovery certificate metadata logic
    # The RecoveryReplayResult contains executor_metadata which populates the certificate
    cut = _create_mock_cut("REPLACE", "A", "fixed")
    env = _create_mock_envelope(cut)
    ctx = ReplayContext(original_trace_id="0" * 32, original_spans=[])

    executor = LocalPipelineRecoveryReplayExecutor(pipeline_factory=MockPipeline)
    with patch(
        "packages.recovery.src.replay_executor.SandboxedWorker.run", side_effect=_mock_sandbox_run
    ):
        result = executor.replay(None, cut, env, ctx)

    assert result.executor_metadata["simulated"] is False
    assert result.executor_metadata["executor"] == "LocalPipelineRecoveryReplayExecutor"
    assert result.target_failure_status == "resolved"
