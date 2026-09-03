import pytest

from packages.diffusion.src.clearance import GATClearanceOracle
from packages.diffusion.src.contracts import DiffusionOutput, GraphDiffusionResult, NodeExplanation
from packages.replay.src.sandbox import SandboxedWorker
from packages.replay.src.vti_coordinator import vti_coordinator


def dummy_agent_action():
    # Simulates an agent trying to write to the database / filesystem in the sandbox
    with open("production_db.txt", "w") as f:
        f.write("DRAFT_EMAIL: Hello World")
    return "Action Completed"


def test_vti_2pc_commit_flow():
    trace_id = "trace_safe_123"

    # 1. Agent executes in sandbox. The file write should be intercepted and staged.
    with pytest.raises(RuntimeError) as exc:
        SandboxedWorker.run(dummy_agent_action, inputs={}, trace_id=trace_id)

    assert "File write staged and blocked" in str(exc.value)

    # 2. Check VTI escrow
    staged = vti_coordinator.get_staged_actions(trace_id)
    assert len(staged) == 1
    assert staged[0].action_type == "FILE_WRITE"
    assert staged[0].status == "STAGED"

    # 3. Simulate GAT Analysis (Safe Trajectory)
    safe_result = GraphDiffusionResult(
        model_version="v2",
        num_steps=1,
        aggregation_method="mean",
        normalization_applied=True,
        node_outputs={
            "node_1": DiffusionOutput(
                node_id="node_1",
                root_probability=0.1,  # Safe (< 0.5)
                symptom_probability=0.1,
                uncertainty=0.01,
                explanation=NodeExplanation(),
            )
        },
    )

    oracle = GATClearanceOracle(drift_threshold=0.5)
    committed = oracle.evaluate_trajectory(trace_id, safe_result)

    assert committed is True
    # The escrow should be cleared from pending and moved to committed
    assert len(vti_coordinator.get_staged_actions(trace_id)) == 0
    assert any(
        a.trace_id == trace_id and a.status == "COMMITTED"
        for a in vti_coordinator.committed_actions
    )


def test_vti_2pc_rollback_flow():
    trace_id = "trace_drift_456"

    # 1. Agent executes in sandbox.
    with pytest.raises(RuntimeError):
        SandboxedWorker.run(dummy_agent_action, inputs={}, trace_id=trace_id)

    # 2. Simulate GAT Analysis (Drift Detected)
    drift_result = GraphDiffusionResult(
        model_version="v2",
        num_steps=1,
        aggregation_method="mean",
        normalization_applied=True,
        node_outputs={
            "node_1": DiffusionOutput(
                node_id="node_1",
                root_probability=0.85,  # Unsafe (>= 0.5)
                symptom_probability=0.9,
                uncertainty=0.01,
                explanation=NodeExplanation(),
            )
        },
    )

    oracle = GATClearanceOracle(drift_threshold=0.5)
    rolled_back = oracle.evaluate_trajectory(trace_id, drift_result)

    # We should have successfully invoked rollback (returns True on success)
    assert rolled_back is True

    # The escrow should be cleared from pending
    assert len(vti_coordinator.get_staged_actions(trace_id)) == 0
    # The action should NOT be in the committed list
    assert not any(
        a.trace_id == trace_id and a.status == "COMMITTED"
        for a in vti_coordinator.committed_actions
    )
