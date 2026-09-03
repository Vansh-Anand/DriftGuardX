"""
DriftGuard-X v2 — Non-Target State Invariance Verification
PRIVATE — All Rights Reserved.
"""

from typing import Any

from packages.contracts.src.recovery_models import ReplayStateManifest


class ContaminationError(Exception):
    """Raised when un-targeted nodes diverge during a replay."""

    pass


class InvarianceChecker:
    """
    Verifies that during a counterfactual replay, no variables outside of the
    explicit 'allowed_causal_descendants' or 'intervened_variables' changed state.
    """

    @staticmethod
    def verify_no_contamination(
        original_manifest: ReplayStateManifest,
        replay_manifest: ReplayStateManifest,
        allowed_causal_descendants: list[str],
        intervened_variables: list[str],
    ) -> dict[str, Any]:
        """
        Compare the post-replay manifest to the pre-replay manifest.
        Any divergence not listed in allowed paths raises ContaminationError.
        """
        divergences = {}

        # Check task state
        for key, original_value in original_manifest.task_state.items():
            if key in allowed_causal_descendants or key in intervened_variables:
                continue

            replay_value = replay_manifest.task_state.get(key)
            if replay_value != original_value:
                divergences[key] = {"expected": original_value, "actual": replay_value}

        # Check prompts (must remain perfectly frozen unless intervened)
        for key, original_prompt in original_manifest.prompts.items():
            if key in intervened_variables:
                continue

            replay_prompt = replay_manifest.prompts.get(key)
            if replay_prompt != original_prompt:
                divergences[f"prompt:{key}"] = {
                    "expected": original_prompt,
                    "actual": replay_prompt,
                }

        if divergences:
            raise ContaminationError(
                f"Contamination detected! Replay mutated non-target state: {divergences}"
            )

        return {"status": "clean"}
