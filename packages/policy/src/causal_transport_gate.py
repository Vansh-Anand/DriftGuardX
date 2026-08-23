"""
DriftGuard-X v2 — Causal Recovery Transportability Gate
PRIVATE — All Rights Reserved.
"""
import hmac

from packages.contracts.src.transport_models import (
    CausalEnvironmentDescriptor,
    EnvironmentDifference,
    RecoveryMechanismFootprint,
    TransportabilityDecision,
    TransportStatus,
)


class CausalTransportGate:
    """
    Evaluates whether a validated recovery from a source environment 
    can be transported to a target environment using its causal footprint.
    """

    def __init__(self, verification_key: str):
        self.verification_key = verification_key

    def _verify_descriptor(self, descriptor: CausalEnvironmentDescriptor) -> bool:
        """Verify the cryptographic HMAC-SHA256 signature of the environment."""
        if not descriptor.signature:
            return False
        expected_sig = descriptor.recompute_signature(self.verification_key)
        return hmac.compare_digest(expected_sig, descriptor.signature)

    def _find_differences(
        self, source: CausalEnvironmentDescriptor, target: CausalEnvironmentDescriptor
    ) -> list[EnvironmentDifference]:
        differences = []

        # Helper to add diff
        def add_diff(var: str, s_val: str, t_val: str, affected: list[str], relevance: float):
            if s_val != t_val:
                differences.append(EnvironmentDifference(
                    variable=var,
                    source_value_hash=s_val,
                    target_value_hash=t_val,
                    affected_components=affected,
                    causal_relevance=relevance,
                    transport_risk=relevance * 0.8
                ))

        add_diff("model", source.model, target.model, ["generator"], 1.0)
        add_diff("prompt", source.prompt, target.prompt, ["prompt"], 0.8)
        add_diff("retriever", source.retriever, target.retriever, ["retriever", "index"], 0.9)
        add_diff("policy", source.policy, target.policy, ["guardrail"], 1.0)
        add_diff("index", source.index, target.index, ["retriever"], 0.7)
        add_diff("data_distribution", source.data_distribution_fingerprint, target.data_distribution_fingerprint, ["model", "index"], 0.6)

        return differences

    def evaluate_transportability(
        self,
        source_env: CausalEnvironmentDescriptor,
        target_env: CausalEnvironmentDescriptor,
        footprint: RecoveryMechanismFootprint,
        allow_cross_tenant: bool = False
    ) -> TransportabilityDecision:
        """
        Determines the transportability of the recovery.
        """
        # 1. Cryptographic Authentication & Evidence Check
        if not self._verify_descriptor(source_env) or not self._verify_descriptor(target_env):
            return self._build_decision(
                footprint.recovery_id, source_env, target_env, TransportStatus.NOT_TRANSPORTABLE,
                [], [], [], "Forged or missing provenance signature."
            )

        if not source_env.calibration_evidence or not target_env.calibration_evidence:
            return self._build_decision(
                footprint.recovery_id, source_env, target_env, TransportStatus.UNKNOWN,
                [], [], [], "Missing structured calibration evidence."
            )

        # 2. Cross-Tenant Policy
        if source_env.tenant_id != target_env.tenant_id and not allow_cross_tenant:
            return self._build_decision(
                footprint.recovery_id, source_env, target_env, TransportStatus.NOT_TRANSPORTABLE,
                [], [], [], "Cross-tenant transport denied by policy."
            )

        # 3. Compute Environment Differences
        differences = self._find_differences(source_env, target_env)

        # 4. Evaluate against Recovery Mechanism Footprint
        violated_conditions = []
        preserved_conditions = []
        unknown_conditions = []
        target_validation_required = False

        critical_mismatch = False

        for diff in differences:
            # Check if this difference breaks a required condition
            var_name = diff.variable

            # Example heuristic check against footprint assumptions
            if var_name in footprint.required_policy_conditions and diff.causal_relevance >= 1.0 or var_name in footprint.required_data_conditions:
                critical_mismatch = True
                violated_conditions.append(var_name)
            elif diff.causal_relevance >= 0.8:
                # Highly relevant but perhaps not strictly breaking if tested
                target_validation_required = True
                unknown_conditions.append(var_name)
            else:
                target_validation_required = True
                unknown_conditions.append(var_name)

        if not differences:
            preserved_conditions = ["all"]

        # 5. Determine Final Status
        if critical_mismatch:
            status = TransportStatus.NOT_TRANSPORTABLE
            explanation = "Critical causal mechanism mismatch."
        elif target_validation_required:
            status = TransportStatus.TARGET_VALIDATION_REQUIRED
            explanation = "Differences exist that require safe target validation experiments."
        elif not differences:
            status = TransportStatus.DIRECTLY_TRANSPORTABLE
            explanation = "All critical recovery mechanism assumptions are preserved."
        else:
            status = TransportStatus.UNKNOWN
            explanation = "Insufficient evidence to determine transportability."

        return self._build_decision(
            footprint.recovery_id,
            source_env,
            target_env,
            status,
            preserved_conditions,
            violated_conditions,
            unknown_conditions,
            explanation
        )

    def _build_decision(
        self, rec_id: str, src: CausalEnvironmentDescriptor, tgt: CausalEnvironmentDescriptor,
        status: TransportStatus, preserved: list[str], violated: list[str], unknown: list[str], explanation: str
    ) -> TransportabilityDecision:

        # Mocking the generation of target experiments if validation is required
        experiments = []
        if status == TransportStatus.TARGET_VALIDATION_REQUIRED:
            for unk in unknown:
                experiments.append({"target_variable": unk, "type": "causal_intervention"})

        decision = TransportabilityDecision(
            recovery_id=rec_id,
            source_environment=src.environment_id,
            target_environment=tgt.environment_id,
            status=status,
            preserved_conditions=preserved,
            violated_conditions=violated,
            unknown_conditions=unknown,
            required_target_experiments=experiments,
            confidence_metadata={"evidence_strength": "high"},
            explanation=explanation
        )
        decision.decision_hash = decision.compute_hash()
        return decision
