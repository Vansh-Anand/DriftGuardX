"""
DriftGuard-X v2 — Cross-deployment Transfer Guard
Update 6: Tests provenance similarity before reusing diagnoses across tenants.
"""
from typing import Dict, Any, Tuple
from packages.contracts.src.models import DGXBaseModel

class SimilarityResult(DGXBaseModel):
    score: float
    matched_anchors: int
    unrecognized_penalties: int

class TransferGuard:
    """
    Credible multi-tenant safety boundary.
    Before a diagnosis or recovery can be reused across tenants or models,
    this guard tests provenance similarity and calibration shift.
    """
    
    @staticmethod
    def _compute_provenance_similarity(source_prov: Dict[str, Any], target_prov: Dict[str, Any]) -> SimilarityResult:
        """
        Computes weighted similarity between sets of critical tools, prompt versions, and models.
        Assigns higher weight to models (3.0), prompts (2.0), tools (1.0).
        Penalizes unrecognized/untrusted nodes heavily to defeat dummy-node Jaccard spoofing.
        """
        weights = {
            "model:": 3.0,
            "prompt:": 2.0,
            "tool:": 1.0
        }
        
        def _parse_components(components) -> Tuple[Dict[str, float], int]:
            parsed = {}
            unrecognized = 0
            for c in components:
                if not isinstance(c, str):
                    continue
                matched = False
                for prefix, weight in weights.items():
                    if c.startswith(prefix):
                        parsed[c] = weight
                        matched = True
                        break
                if not matched:
                    unrecognized += 1
            return parsed, unrecognized
            
        source_nodes, source_unrec = _parse_components(source_prov.get("components", []))
        target_nodes, target_unrec = _parse_components(target_prov.get("components", []))
        
        if not source_nodes and not target_nodes:
            # If both are empty, similarity is 1.0 but they have no critical nodes.
            # If there are unrecognized nodes, we penalize.
            score = 1.0 if source_unrec == 0 and target_unrec == 0 else 0.0
            return SimilarityResult(score=score, matched_anchors=0, unrecognized_penalties=source_unrec + target_unrec)
            
        intersection = set(source_nodes.keys()).intersection(target_nodes.keys())
        union = set(source_nodes.keys()).union(target_nodes.keys())
        
        intersection_weight = sum(source_nodes[n] for n in intersection)
        union_weight = sum(source_nodes.get(n, target_nodes.get(n, 1.0)) for n in union)
        
        # Base Jaccard on weights
        raw_score = intersection_weight / union_weight if union_weight > 0 else 0.0
        
        # Penalize for unrecognized nodes to defeat spoofing attempts (e.g., -0.2 per dummy node)
        penalty = (source_unrec + target_unrec) * 0.2
        final_score = max(0.0, raw_score - penalty)
        
        return SimilarityResult(
            score=final_score,
            matched_anchors=len(intersection),
            unrecognized_penalties=source_unrec + target_unrec
        )

    @staticmethod
    def can_transfer_diagnosis(
        source_tenant_id: str, 
        target_tenant_id: str, 
        source_provenance: Dict[str, Any], 
        target_provenance: Dict[str, Any],
        calibration_shift: float,
        similarity_threshold: float = 0.8,
        max_calibration_shift: float = 0.1
    ) -> bool:
        """
        Evaluates whether a diagnosis from a source tenant can safely be applied to a target tenant.
        """
        # If it's the same tenant, transfer is usually safe
        if source_tenant_id == target_tenant_id:
            return True
            
        result = TransferGuard._compute_provenance_similarity(source_provenance, target_provenance)
        
        if result.score < similarity_threshold:
            return False
            
        # Check if the calibration bounds shifted significantly between the two deployments
        if calibration_shift > max_calibration_shift:
            return False
            
        return True
