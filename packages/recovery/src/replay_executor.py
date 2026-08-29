"""
DriftGuard-X v2 — Recovery Replay Execution Architecture
PRIVATE — All Rights Reserved.
"""
from collections.abc import Callable
from typing import Any

from packages.contracts.src.interfaces import RecoveryReplayExecutor
from packages.contracts.src.recovery_models import (
    CausalRecoveryCut,
    RecoveryActionType,
    RecoveryReplayResult,
    ReplayContext,
    ReplayEquivalenceEnvelope,
    SandboxOutcome,
)
from packages.replay.src.exogenous_controller import ExogenousStateController
from packages.replay.src.sandbox import SandboxedWorker


class SyntheticRecoveryReplayExecutor(RecoveryReplayExecutor):
    """
    Simulates recovery replay by directly mutating the stored historical spans.
    This replaces the legacy _run_controlled_replay behavior.
    MUST ONLY be used when DGX_MODE != "production".
    """
    def replay(
        self,
        original_execution: Any,
        recovery_cut: CausalRecoveryCut,
        envelope: ReplayEquivalenceEnvelope,
        context: ReplayContext,
    ) -> RecoveryReplayResult:
        result_spans = list(context.original_spans)

        # Apply the recovery cut: mutate the intervened components
        for action in recovery_cut.selected_actions:
            for i, span in enumerate(result_spans):
                if span.get("component_type") == action.target_component:
                    result_spans[i] = {
                        **span,
                        "output": {"status": "recovered", "action": getattr(action, "action_type", None)},
                        "_intervened": True,
                    }

        metrics = {
            "regression_count": float(recovery_cut.regression_risk),
            "blast_radius": float(recovery_cut.blast_radius),
        }

        return RecoveryReplayResult(
            outcome=SandboxOutcome.SUCCESS,
            new_trace_id=envelope.trace_id,
            new_spans=result_spans,
            new_state_snapshot=None,
            target_failure_status="recovered",
            metrics=metrics,
            executor_metadata={"simulated": True, "executor": "SyntheticRecoveryReplayExecutor"}
        )


class RecoveryActionApplier:
    """Applies the recovery action to the pipeline state or dependencies."""
    def apply(self, action: Any, pipeline: Any) -> bool:
        """Returns True if the action is supported and successfully applied."""
        action_type = getattr(action, "action_type", None)
        if isinstance(action_type, str):
            try:
                action_type = RecoveryActionType(action_type)
            except ValueError:
                return False

        if action_type in (RecoveryActionType.REPLACE, RecoveryActionType.ROLLBACK, RecoveryActionType.RECONFIGURE):
            # In a real environment, this applies the patch to the running process
            if hasattr(pipeline, "apply_patch"):
                pipeline.apply_patch(action.target_component, action.replacement)
                return True
            return False

        return False


class LocalPipelineRecoveryReplayExecutor(RecoveryReplayExecutor):
    """
    Executes a real local pipeline with recovery actions applied inside a sandbox.
    """
    def __init__(self, pipeline_factory: Callable[[], Any], applier: RecoveryActionApplier | None = None):
        self.pipeline_factory = pipeline_factory
        self.applier = applier or RecoveryActionApplier()

    def replay(
        self,
        original_execution: Any,
        recovery_cut: CausalRecoveryCut,
        envelope: ReplayEquivalenceEnvelope,
        context: ReplayContext,
    ) -> RecoveryReplayResult:
        exogenous_vars = envelope.exogenous_variables

        def _replay_fn(**kwargs: Any) -> dict[str, Any]:
            pipeline = self.pipeline_factory()

            # Apply all actions
            for action in recovery_cut.selected_actions:
                success = self.applier.apply(action, pipeline)
                if not success:
                    return {"_error": "ACTION_UNSUPPORTED", "action": getattr(action, "action_id", "unknown")}

            # Execute
            try:
                result = pipeline.execute(context.config)
            except Exception as e:
                return {"_error": "REPLAY_EXECUTION_FAILURE", "details": str(e)}

            return {
                "spans": getattr(result, "spans", result.get("spans", []) if isinstance(result, dict) else []),
                "metrics": getattr(result, "metrics", result.get("metrics", {}) if isinstance(result, dict) else {}),
                "state_snapshot": getattr(result, "state_snapshot", result.get("state_snapshot", None) if isinstance(result, dict) else None),
                "failure_status": getattr(result, "failure_status", result.get("failure_status", "unresolved") if isinstance(result, dict) else "unresolved")
            }

        try:
            with ExogenousStateController.from_envelope_vars(exogenous_vars):
                result = SandboxedWorker.run(
                    func=_replay_fn,
                    inputs={},
                    timeout_seconds=30,
                    trace_id=envelope.trace_id,
                )
        except Exception as e:
            # DO NOT FALL BACK TO UNSAFE EXECUTION IN PRODUCTION
            return RecoveryReplayResult(
                outcome=SandboxOutcome.SANDBOX_UNAVAILABLE,
                executor_metadata={"error": str(e), "executor": "LocalPipelineRecoveryReplayExecutor"}
            )

        if "_error" in result:
            outcome_mapping = {
                "ACTION_UNSUPPORTED": SandboxOutcome.ACTION_UNSUPPORTED,
                "REPLAY_EXECUTION_FAILURE": SandboxOutcome.REPLAY_EXECUTION_FAILURE,
            }
            return RecoveryReplayResult(
                outcome=outcome_mapping.get(result["_error"], SandboxOutcome.REPLAY_EXECUTION_FAILURE),
                executor_metadata={"error_details": result, "executor": "LocalPipelineRecoveryReplayExecutor"}
            )

        metrics = {
            "regression_count": float(result.get("metrics", {}).get("regression_count", recovery_cut.regression_risk)),
            "blast_radius": float(result.get("metrics", {}).get("blast_radius", recovery_cut.blast_radius)),
        }

        return RecoveryReplayResult(
            outcome=SandboxOutcome.SUCCESS,
            new_trace_id=envelope.trace_id,
            new_spans=result.get("spans", []),
            new_state_snapshot=result.get("state_snapshot", None),
            target_failure_status=result.get("failure_status", "unresolved"),
            metrics=metrics,
            executor_metadata={"simulated": False, "executor": "LocalPipelineRecoveryReplayExecutor"}
        )
