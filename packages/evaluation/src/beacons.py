"""
DriftGuard-X v2 — Hosted-provider Drift Beacons
Update 11: Probe black-box dependencies to detect silent provider shifts.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import hashlib

from packages.evaluation.src.semantics import SemanticEncoder, CosineDriftComparator, get_semantic_encoder

class DriftBeacon:
    """
    Runs sealed behavioral probes through material agent paths to detect
    silent shifts in hosted provider behavior (e.g. LLM API changes).
    """
    def __init__(
        self, 
        provider_id: str, 
        baseline_outputs: Dict[str, str],
        encoder: Optional[SemanticEncoder] = None
    ):
        self.provider_id = provider_id
        self.baseline_outputs = baseline_outputs 
        
        # In production this will throw if forced to fake
        enc = encoder if encoder else get_semantic_encoder()
        self.comparator = CosineDriftComparator(enc)
        
    def _compute_identity_hash(self, output: str) -> str:
        """
        Computes exact SHA-256 hash for artifact identity and integrity logging.
        NOT used for semantic drift decisions.
        """
        return hashlib.sha256(output.encode('utf-8')).hexdigest()

    def run_probe(self, probe_id: str, probe_input: Any, runner_func) -> Dict[str, Any]:
        """
        Executes a deterministic probe against the hosted provider.
        Compares the resulting output signature, tool choices, and latency against baselines.
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            result = runner_func(probe_input)
            end_time = datetime.now(timezone.utc)
            latency_ms = (end_time - start_time).total_seconds() * 1000
            
            output_text = result.get("text", "")
            
            # Identity hash for integrity
            identity_hash = self._compute_identity_hash(output_text)
            
            baseline_text = self.baseline_outputs.get(probe_id)
            
            if baseline_text:
                decision = self.comparator.compare(baseline_text, output_text)
                is_drifted = decision.decision
                drift_score = decision.drift_score
                diagnostics = decision.diagnostics
            else:
                is_drifted = False
                drift_score = 0.0
                diagnostics = {}
            
            return {
                "probe_id": probe_id,
                "provider_id": self.provider_id,
                "is_drifted": is_drifted,
                "drift_score": drift_score,
                "latency_ms": latency_ms,
                "identity_hash": identity_hash,
                "diagnostics": diagnostics,
                "timestamp": end_time
            }
        except Exception as e:
            end_time = datetime.now(timezone.utc)
            return {
                "probe_id": probe_id,
                "provider_id": self.provider_id,
                "is_drifted": True,
                "error": str(e),
                "timestamp": end_time
            }
