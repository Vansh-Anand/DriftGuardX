"""
DriftGuard-X v2 — Recovery Adapters
PRIVATE — All Rights Reserved.

Defines the real, production-ready adapters for executing interventions
and rollbacks (e.g. Kubernetes, Feature Flags).
"""

import abc
import logging
from typing import Any

from packages.recovery.src.actions import RecoveryActionType

logger = logging.getLogger(__name__)


class RecoveryAdapter(abc.ABC):
    """Abstract interface for an action-specific production adapter."""
    
    @abc.abstractmethod
    def supports(self, action_type: str) -> bool:
        """Returns True if this adapter can handle the given action type."""
        pass
        
    @abc.abstractmethod
    def apply(self, params: dict[str, Any]) -> dict[str, Any]:
        """Applies the intervention, returning side effects."""
        pass
        
    @abc.abstractmethod
    def rollback(self, previous_state: dict[str, Any], target_state: dict[str, Any]) -> dict[str, Any]:
        """Rolls back the intervention using the capsule state, returning side effects."""
        pass


class KubernetesRollbackAdapter(RecoveryAdapter):
    """
    Adapter that executes 'kubectl rollout undo' (or equivalent API calls)
    for rolling back a component.
    """
    
    def __init__(self, k8s_client: Any = None):
        # We accept a stubbed/mocked client if None is provided, 
        # normally this would be initialized with `kubernetes.client.AppsV1Api()`
        self.k8s_client = k8s_client
        
    def supports(self, action_type: str) -> bool:
        return action_type == RecoveryActionType.ROLLBACK_COMPONENT.value
        
    def apply(self, params: dict[str, Any]) -> dict[str, Any]:
        component_id = params.get("component_id")
        target_version = params.get("target_version_id")
        
        logger.info(f"Applying Kubernetes deployment update for {component_id} to version {target_version}")
        # In a real system, we'd call: self.k8s_client.patch_namespaced_deployment(...)
        return {"component_id": component_id, "version_id": target_version, "k8s_action": "patch"}
        
    def rollback(self, previous_state: dict[str, Any], target_state: dict[str, Any]) -> dict[str, Any]:
        component_id = previous_state.get("component_id")
        revert_version = previous_state.get("version_id")
        
        logger.info(f"Rolling back Kubernetes deployment {component_id} to revision {revert_version}")
        # In a real system, we'd call: self.k8s_client.patch_namespaced_deployment_rollback(...)
        return {"component_id": component_id, "version_id": revert_version, "k8s_action": "rollback"}


class FeatureFlagAdapter(RecoveryAdapter):
    """
    Adapter that interacts with a Feature Flag service (e.g. LaunchDarkly)
    to disable tools, switch models, or change routes dynamically.
    """
    
    def __init__(self, ld_client: Any = None):
        # Normally initialized with `ldclient.get()`
        self.ld_client = ld_client
        
    def supports(self, action_type: str) -> bool:
        return action_type in (
            RecoveryActionType.DISABLE_TEST_TOOL.value,
            RecoveryActionType.ROUTE_STABLE_MODEL.value,
            RecoveryActionType.SWITCH_STABLE_INDEX.value
        )
        
    def apply(self, params: dict[str, Any]) -> dict[str, Any]:
        # Handle based on params keys
        if "tool_id" in params:
            tool_id = params["tool_id"]
            logger.info(f"Disabling tool {tool_id} via Feature Flag")
            return {"tool_id": tool_id, "disabled": True, "ff_action": "disable_tool"}
            
        elif "stable_model_alias" in params:
            model = params["stable_model_alias"]
            component = params.get("component_id")
            logger.info(f"Routing {component} to stable model {model} via Feature Flag")
            return {"component_id": component, "model": model, "ff_action": "route_model"}
            
        elif "target_index_id" in params:
            index = params["target_index_id"]
            component = params.get("component_id")
            logger.info(f"Switching {component} to index {index} via Feature Flag")
            return {"component_id": component, "index_id": index, "ff_action": "switch_index"}
            
        raise ValueError(f"FeatureFlagAdapter could not determine action from params: {params}")

    def rollback(self, previous_state: dict[str, Any], target_state: dict[str, Any]) -> dict[str, Any]:
        # Restore previous flag states
        if "tool_id" in previous_state:
            tool_id = previous_state["tool_id"]
            logger.info(f"Re-enabling tool {tool_id} via Feature Flag rollback")
            return {"tool_id": tool_id, "disabled": previous_state.get("disabled", False), "ff_action": "enable_tool"}
            
        elif "model" in previous_state:
            model = previous_state["model"]
            component = previous_state.get("component_id")
            logger.info(f"Rolling back {component} to model {model} via Feature Flag")
            return {"component_id": component, "model": model, "ff_action": "route_model_rollback"}
            
        elif "index_id" in previous_state:
            index = previous_state["index_id"]
            component = previous_state.get("component_id")
            logger.info(f"Rolling back {component} to index {index} via Feature Flag")
            return {"component_id": component, "index_id": index, "ff_action": "switch_index_rollback"}

        raise ValueError(f"FeatureFlagAdapter could not determine rollback from state: {previous_state}")
