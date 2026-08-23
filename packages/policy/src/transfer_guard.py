"""
DriftGuard-X v2 — Cross-deployment Transfer Guard
Update 6: Tests provenance similarity before reusing diagnoses across tenants.
Update 13: Cryptographically authenticated provenance envelopes.
"""
import hashlib

from pydantic import BaseModel

from packages.contracts.src.transport_models import (
    CausalEnvironmentDescriptor,
    RecoveryMechanismFootprint,
    TransportabilityDecision,
)
from packages.policy.src.causal_transport_gate import CausalTransportGate


class SimilarityResult(BaseModel):
    score: float
    matched_anchors: int
    unrecognized_penalties: int

class CalibrationEvidence(BaseModel):
    confidence_interval: float
    support_size: int
    empirical_risk: float

class ProvenanceEnvelope(BaseModel):
    tenant_id: str
    components: list[str]
    environment_hash: str
    calibration_evidence: CalibrationEvidence
    signature: str | None = None

    def recompute_signature(self, secret_key: str) -> str:
        import base64
        import hmac
        comps = ",".join(sorted(self.components))
        data = f"{self.tenant_id}|{comps}|{self.environment_hash}|{self.calibration_evidence.confidence_interval}|{self.calibration_evidence.support_size}|{self.calibration_evidence.empirical_risk}".encode()
        mac = hmac.new(secret_key.encode('utf-8'), data, hashlib.sha256).digest()
        return base64.b64encode(mac).decode('utf-8')

class TransferGuard:
    """
    Credible multi-tenant safety boundary.
    Before a diagnosis or recovery can be reused across tenants or models,
    this guard tests provenance similarity and calibration shift using
    cryptographically verified envelopes.
    """
    def __init__(self, verification_key: str):
        self.verification_key = verification_key

    def _verify_envelope(self, envelope: ProvenanceEnvelope) -> bool:
        """Verifies that the provenance envelope was signed by a trusted authority."""
        if not envelope.signature:
            return False
        import hmac
        expected_sig = envelope.recompute_signature(self.verification_key)
        return hmac.compare_digest(expected_sig, envelope.signature)

    def _compute_provenance_similarity(self, source_env: ProvenanceEnvelope, target_env: ProvenanceEnvelope) -> SimilarityResult:
        """
        Computes weighted similarity between sets of critical tools, prompt versions, and models.
        Assigns higher weight to models (3.0), prompts (2.0), tools (1.0).
        """
        weights = {
            "model:": 3.0,
            "agent:": 2.5,
            "prompt:": 2.0,
            "tool:": 1.0,
            "data:": 1.0
        }

        def _parse_components(components: list[str]) -> tuple[dict[str, float], int]:
            parsed = {}
            unrecognized = 0
            for c in components:
                matched = False
                for prefix, weight in weights.items():
                    if c.startswith(prefix):
                        parsed[c] = weight
                        matched = True
                        break
                if not matched:
                    unrecognized += 1
            return parsed, unrecognized

        source_nodes, source_unrec = _parse_components(source_env.components)
        target_nodes, target_unrec = _parse_components(target_env.components)

        if not source_nodes and not target_nodes:
            score = 1.0 if source_unrec == 0 and target_unrec == 0 else 0.0
            return SimilarityResult(score=score, matched_anchors=0, unrecognized_penalties=source_unrec + target_unrec)

        intersection = set(source_nodes.keys()).intersection(target_nodes.keys())
        union = set(source_nodes.keys()).union(target_nodes.keys())

        intersection_weight = sum(source_nodes[n] for n in intersection)
        union_weight = sum(source_nodes.get(n, target_nodes.get(n, 1.0)) for n in union)

        raw_score = intersection_weight / union_weight if union_weight > 0 else 0.0
        penalty = (source_unrec + target_unrec) * 0.2
        final_score = max(0.0, raw_score - penalty)

        return SimilarityResult(
            score=final_score,
            matched_anchors=len(intersection),
            unrecognized_penalties=source_unrec + target_unrec
        )

    def can_transfer_diagnosis(
        self,
        source_provenance: ProvenanceEnvelope,
        target_provenance: ProvenanceEnvelope,
        similarity_threshold: float = 0.8,
        max_calibration_shift: float = 0.1
    ) -> bool:
        """
        Evaluates whether a diagnosis from a source tenant can safely be applied to a target tenant.
        """
        # Cryptographic verification MUST pass before any parsing
        if not self._verify_envelope(source_provenance) or not self._verify_envelope(target_provenance):
            return False

        # If it's the same tenant and exact environment, transfer is safe
        if source_provenance.tenant_id == target_provenance.tenant_id and source_provenance.environment_hash == target_provenance.environment_hash:
            return True

        result = self._compute_provenance_similarity(source_provenance, target_provenance)

        if result.score < similarity_threshold:
            return False

        # Check if the calibration bounds shifted significantly between the two deployments
        calibration_shift = abs(source_provenance.calibration_evidence.empirical_risk - target_provenance.calibration_evidence.empirical_risk)
        if calibration_shift > max_calibration_shift:
            return False

        return True

    def evaluate_causal_transportability(
        self,
        source_env: CausalEnvironmentDescriptor,
        target_env: CausalEnvironmentDescriptor,
        footprint: RecoveryMechanismFootprint,
        allow_cross_tenant: bool = False
    ) -> TransportabilityDecision:
        """
        Advanced transportability check using causal footprints.
        Replaces simple Jaccard similarity.
        """
        gate = CausalTransportGate(self.verification_key)
        return gate.evaluate_transportability(source_env, target_env, footprint, allow_cross_tenant)
