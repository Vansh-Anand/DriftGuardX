import uuid
from packages.recovery.src.actions import RecoveryActionType, RecoveryProposal, ExecutionMode
from packages.recovery.src.capsule import CapsuleRegistry
from packages.recovery.src.executor import ProductionExecutor
from packages.recovery.src.adapters import KubernetesRollbackAdapter, FeatureFlagAdapter

def test_kubernetes_adapter_apply_and_rollback():
    adapter = KubernetesRollbackAdapter()
    
    assert adapter.supports(RecoveryActionType.ROLLBACK_COMPONENT.value)
    
    # Apply
    params = {"component_id": "api-deployment", "target_version_id": "v2"}
    side_effects = adapter.apply(params)
    assert side_effects == {"component_id": "api-deployment", "version_id": "v2", "k8s_action": "patch"}
    
    # Rollback
    prev_state = {"component_id": "api-deployment", "version_id": "v1"}
    target_state = {"component_id": "api-deployment", "version_id": "v2"}
    rb_effects = adapter.rollback(prev_state, target_state)
    assert rb_effects == {"component_id": "api-deployment", "version_id": "v1", "k8s_action": "rollback"}


def test_feature_flag_adapter_apply_and_rollback():
    adapter = FeatureFlagAdapter()
    
    assert adapter.supports(RecoveryActionType.DISABLE_TEST_TOOL.value)
    assert adapter.supports(RecoveryActionType.ROUTE_STABLE_MODEL.value)
    assert adapter.supports(RecoveryActionType.SWITCH_STABLE_INDEX.value)
    
    # Disable tool
    se = adapter.apply({"tool_id": "dangerous_tool"})
    assert se == {"tool_id": "dangerous_tool", "disabled": True, "ff_action": "disable_tool"}
    
    rb = adapter.rollback({"tool_id": "dangerous_tool", "disabled": False}, {})
    assert rb == {"tool_id": "dangerous_tool", "disabled": False, "ff_action": "enable_tool"}
    
    # Route model
    se = adapter.apply({"component_id": "reasoning_agent", "stable_model_alias": "gpt-4-stable"})
    assert se == {"component_id": "reasoning_agent", "model": "gpt-4-stable", "ff_action": "route_model"}
    
    rb = adapter.rollback({"component_id": "reasoning_agent", "model": "gpt-4-old"}, {})
    assert rb == {"component_id": "reasoning_agent", "model": "gpt-4-old", "ff_action": "route_model_rollback"}
    
    # Switch index
    se = adapter.apply({"component_id": "retrieval_agent", "target_index_id": "index_v2"})
    assert se == {"component_id": "retrieval_agent", "index_id": "index_v2", "ff_action": "switch_index"}
    
    rb = adapter.rollback({"component_id": "retrieval_agent", "index_id": "index_v1"}, {})
    assert rb == {"component_id": "retrieval_agent", "index_id": "index_v1", "ff_action": "switch_index_rollback"}


def test_production_executor():
    registry = CapsuleRegistry()
    executor = ProductionExecutor(capsule_registry=registry)
    
    # Test executing an action
    proposal = RecoveryProposal(
        proposal_id="prop-prod-1",
        action_type=RecoveryActionType.DISABLE_TEST_TOOL,
        tenant_id="tenant-1",
        node_id="node-1",
        run_id=str(uuid.uuid4()),
        diagnosis_id="diag-1",
        params={"tool_id": "bad_tool"},
        execution_mode=ExecutionMode.APPROVED,
        requester_id="admin",
        policy_decision="approve",
        approval_request_id="app-1"
    )
    
    result = executor.execute(proposal)
    assert result.success is True
    assert result.capsule_id is not None
    assert result.side_effects["disabled"] is True
    
    # Test compensating the action
    capsule = registry.get(result.capsule_id)
    assert capsule is not None
    
    comp_result = executor.compensate(capsule)
    assert comp_result.success is True
    assert comp_result.side_effects["disabled"] is False
    assert comp_result.side_effects["ff_action"] == "enable_tool"
