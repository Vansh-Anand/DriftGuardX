import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException

from apps.api.src.services.recovery_pipeline import EndToEndRecoveryPipeline
from packages.contracts.src.agent_models import AgentInvocation
from packages.contracts.src.models import RecoveryCertificate

router = APIRouter(prefix="/v1/recovery", tags=["recovery"])

# In-memory store for demo purposes
# In a real deployment, this would be a database integration
CERTIFICATE_STORE: list[RecoveryCertificate] = []


@router.get("", response_model=list[RecoveryCertificate])
def list_certificates():
    """
    List all generated recovery certificates.
    """
    return CERTIFICATE_STORE


@router.post("/trigger", response_model=RecoveryCertificate)
def trigger_recovery(payload: dict[str, Any]):
    """
    Manually triggers the recovery pipeline for a given run and failure symptom.
    Expects JSON: {"tenant_id": "...", "run_id": "...", "failure_symptom": "..."}
    """
    tenant_id = payload.get("tenant_id", str(uuid.uuid4()))
    run_id = payload.get("run_id", str(uuid.uuid4()))
    failure_symptom = payload.get("failure_symptom", "Data drift detected")

    pipeline = EndToEndRecoveryPipeline(tenant_id=tenant_id)

    # Generate some mock invocations that would lead up to this failure
    invocations = [
        AgentInvocation(
            invocation_id=uuid.uuid4(),
            run_id=uuid.UUID(run_id),
            tenant_id=uuid.UUID(tenant_id),
            agent_name="retrieval",
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
        ),
        AgentInvocation(
            invocation_id=uuid.uuid4(),
            run_id=uuid.UUID(run_id),
            tenant_id=uuid.UUID(tenant_id),
            agent_name="generator",
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
        ),
    ]

    cert = pipeline.execute_recovery_loop(run_id, invocations, failure_symptom)

    if not cert:
        raise HTTPException(status_code=500, detail="Failed to generate recovery certificate.")

    CERTIFICATE_STORE.append(cert)
    return cert
