import uuid

from packages.recovery.src.actions import ExecutionMode, RecoveryActionType, RecoveryProposal
from packages.recovery.src.capsule import CapsuleRegistry
from packages.recovery.src.executor import ProductionExecutor


def test_production_executor_apply():
    reg = CapsuleRegistry()
    executor = ProductionExecutor(capsule_registry=reg)

    # K8s rollback
    proposal = RecoveryProposal(
        action_type=RecoveryActionType.ROLLBACK_COMPONENT,
        params={
            "component_id": "api",
            "target_version_id": "v2",
            "expected_current_version_id": "v1",
        },
        execution_mode=ExecutionMode.APPROVED,
        tenant_id="t1",
        node_id="node1",
        run_id=uuid.uuid4(),
        diagnosis_id=uuid.uuid4(),
        requester_id="user1",
    )

    res = executor.execute(proposal)
    assert res.success
    assert res.side_effects == {"component_id": "api", "version_id": "v2", "k8s_action": "patch"}
    assert res.capsule_id is not None

    # Feature flag disable
    proposal_ff = RecoveryProposal(
        action_type=RecoveryActionType.DISABLE_TEST_TOOL,
        params={"tool_id": "calculator"},
        execution_mode=ExecutionMode.APPROVED,
        tenant_id="t1",
        node_id="node1",
        run_id=uuid.uuid4(),
        diagnosis_id=uuid.uuid4(),
        requester_id="user1",
    )

    res_ff = executor.execute(proposal_ff)
    assert res_ff.success
    assert res_ff.side_effects == {
        "tool_id": "calculator",
        "disabled": True,
        "ff_action": "disable_tool",
    }


def test_production_executor_rollback():
    reg = CapsuleRegistry()
    executor = ProductionExecutor(capsule_registry=reg)

    proposal = RecoveryProposal(
        action_type=RecoveryActionType.ROLLBACK_COMPONENT,
        params={
            "component_id": "worker",
            "target_version_id": "v2",
            "expected_current_version_id": "current_v1",
        },
        execution_mode=ExecutionMode.APPROVED,
        tenant_id="t1",
        node_id="node1",
        run_id=uuid.uuid4(),
        diagnosis_id=uuid.uuid4(),
        requester_id="user1",
    )

    executor.execute(proposal)
    capsule = reg.for_proposal(proposal.proposal_id)

    # Rollback the action
    comp_res = executor.compensate(capsule)
    assert comp_res.success
    # The previous state mocked in executor uses "current_v1"
    assert comp_res.side_effects == {
        "component_id": "worker",
        "version_id": "current_v1",
        "k8s_action": "rollback",
    }


def test_feature_flag_rollback():
    reg = CapsuleRegistry()
    executor = ProductionExecutor(capsule_registry=reg)

    proposal = RecoveryProposal(
        action_type=RecoveryActionType.DISABLE_TEST_TOOL,
        params={"tool_id": "calculator"},
        execution_mode=ExecutionMode.APPROVED,
        tenant_id="t1",
        node_id="node1",
        run_id=uuid.uuid4(),
        diagnosis_id=uuid.uuid4(),
        requester_id="user1",
    )

    executor.execute(proposal)
    capsule = reg.for_proposal(proposal.proposal_id)

    comp_res = executor.compensate(capsule)
    assert comp_res.success
    assert comp_res.side_effects == {
        "tool_id": "calculator",
        "disabled": False,
        "ff_action": "enable_tool",
    }
