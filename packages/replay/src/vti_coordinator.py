import hashlib
import json
from typing import Any


class CryptographicEscrow:
    """
    Simulates a secure container holding staged actions.
    The payload is hashed for integrity.
    """

    def __init__(self, trace_id: str, action_type: str, payload: dict[str, Any]):
        self.trace_id = trace_id
        self.action_type = action_type
        self.payload = payload

        # Serialize and hash the payload deterministically
        serialized = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.payload_hash = hashlib.sha256(serialized).hexdigest()
        self.status = "STAGED"


class VTICoordinator:
    """
    Two-Phase Commit Database Coordinator for AI Agent execution.
    Acts as the boundary between the sandboxed VTI and the live environment.
    """

    def __init__(self):
        # In-memory storage for escrows mapping trace_id -> List[CryptographicEscrow]
        self._escrows: dict[str, list[CryptographicEscrow]] = {}
        # In-memory mock for committed actions (live environment simulation)
        self.committed_actions: list[CryptographicEscrow] = []

    def stage_action(
        self, trace_id: str, action_type: str, payload: dict[str, Any]
    ) -> CryptographicEscrow:
        """
        Phase 1: Stage the action in a cryptographic escrow.
        """
        escrow = CryptographicEscrow(trace_id, action_type, payload)
        if trace_id not in self._escrows:
            self._escrows[trace_id] = []
        self._escrows[trace_id].append(escrow)
        return escrow

    def commit_action(self, trace_id: str, clearance_signature: str) -> bool:
        """
        Phase 2 (Commit): If the GAT clears the trajectory, commit to the live environment.
        """
        if not clearance_signature or not clearance_signature.startswith("GAT-CLEAR-"):
            raise ValueError(f"Invalid clearance signature for trace {trace_id}")

        escrows = self._escrows.get(trace_id, [])
        if not escrows:
            return False  # Nothing to commit

        for escrow in escrows:
            if escrow.status == "STAGED":
                escrow.status = "COMMITTED"
                self.committed_actions.append(escrow)

        # Clear from staged pool
        del self._escrows[trace_id]
        return True

    def rollback_action(self, trace_id: str) -> bool:
        """
        Phase 2 (Rollback): If GAT detects drift, instantly discard staged actions.
        """
        escrows = self._escrows.get(trace_id, [])
        if not escrows:
            return False

        for escrow in escrows:
            escrow.status = "ROLLED_BACK"

        del self._escrows[trace_id]
        return True

    def get_staged_actions(self, trace_id: str) -> list[CryptographicEscrow]:
        return self._escrows.get(trace_id, [])


# Global instance for simulation scope
vti_coordinator = VTICoordinator()
