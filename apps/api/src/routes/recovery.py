import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.database import get_db
from apps.api.src.services.recovery_pipeline import EndToEndRecoveryPipeline
from packages.contracts.src.agent_models import AgentInvocation
from packages.contracts.src.models import RecoveryCertificate
from apps.api.src.dependencies import require_role
from packages.contracts.src.auth import Role, User
from apps.api.src.models import ApprovalRequestORM, ApprovalDecisionORM

router = APIRouter(prefix="/v1/recovery", tags=["recovery"])

# In-memory store for demo purposes
# In a real deployment, this would be a database integration
CERTIFICATE_STORE: list[RecoveryCertificate] = []


@router.get("", response_model=list[RecoveryCertificate])
def list_certificates(
    current_user: User = Depends(require_role(Role.VIEWER))
):
    """
    List all generated recovery certificates.
    """
    return CERTIFICATE_STORE


@router.post("/trigger")
async def trigger_recovery(payload: dict[str, Any], db: AsyncSession = Depends(get_db), current_user: User = Depends(require_role(Role.ADMIN))):
    """
    Manually triggers the recovery pipeline for a given run and failure symptom.
    """
    # Validate tenant isolation
    tenant_id = payload.get("tenant_id", str(uuid.uuid4()))
    if tenant_id != str(current_user.tenant_id) and Role.SYSTEM not in current_user.roles:
        raise HTTPException(status_code=403, detail="Cross-tenant recovery trigger forbidden")

    run_id = payload.get("run_id", str(uuid.uuid4()))
    failure_symptom = payload.get("failure_symptom", "Data drift detected")

    pipeline = EndToEndRecoveryPipeline(tenant_id=tenant_id)
    invocations = [
        AgentInvocation(
            invocation_id=uuid.uuid4(), run_id=uuid.UUID(run_id), tenant_id=uuid.UUID(tenant_id),
            agent_name="retrieval", start_time=datetime.now(UTC), end_time=datetime.now(UTC),
        )
    ]
    approval_req = await pipeline.execute_recovery_loop(run_id, invocations, failure_symptom, db)

    if not approval_req:
        import traceback; traceback.print_exc(); raise HTTPException(status_code=500, detail="Failed to propose recovery.")

    from apps.api.src.services.audit import AuditService
    await AuditService.log_event(db, uuid.UUID(tenant_id), current_user.id, "RECOVERY_PROPOSED", "Recovery", run_id)
    await db.commit()

    return {"status": "pending_approval", "approval_request_id": str(approval_req.id)}

@router.post("/approve", response_model=RecoveryCertificate)
async def approve_recovery(payload: dict[str, Any], db: AsyncSession = Depends(get_db), current_user: User = Depends(require_role(Role.ADMIN))):
    """Approve a pending recovery and mint the certificate."""
    approval_id = payload.get("approval_id")
    decision = payload.get("decision", "APPROVED")
    
    if not approval_id:
        raise HTTPException(status_code=400, detail="approval_id required")
        
    from sqlalchemy import select
    from apps.api.src.models import ApprovalRequestORM, ApprovalDecisionORM
    from apps.api.src.services.audit import AuditService
    
    result = await db.execute(select(ApprovalRequestORM).where(ApprovalRequestORM.id == uuid.UUID(approval_id)))
    req = result.scalar_one_or_none()
    
    if not req:
        raise HTTPException(status_code=404, detail="Approval request not found")
        
    if req.tenant_id != current_user.tenant_id:
        # Cross-tenant check
        await AuditService.log_event(db, current_user.tenant_id, current_user.id, "CROSS_TENANT_APPROVAL_ATTEMPT", "ApprovalRequest", str(req.id))
        await db.commit()
        raise HTTPException(status_code=403, detail="Cross-tenant access forbidden")
        
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Approval is not pending")
        
    if req.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
        req.status = "expired"
        await db.commit()
        raise HTTPException(status_code=400, detail="Approval request expired")
        
    decision_id = uuid.uuid4()
    decision_orm = ApprovalDecisionORM(
        id=decision_id,
        request_id=req.id,
        actor_id=str(current_user.id),
        decision=decision
    )
    db.add(decision_orm)
    
    if decision != "APPROVED":
        req.status = "rejected"
        await AuditService.log_event(db, req.tenant_id, current_user.id, "RECOVERY_REJECTED", "ApprovalRequest", str(req.id))
        await db.commit()
        raise HTTPException(status_code=400, detail="Recovery rejected")
        
    req.status = "approved"
    
    # Mint Certificate
    from packages.ledger.src.crypto import DevelopmentSigner
    from packages.contracts.src.evidence import RecoveryEvidenceKind
    signer = DevelopmentSigner(key_id="prod-key-v1")
    
    ctx = req.context_json
    import json
    payload_to_sign = {
        "run_id": ctx["run_id"],
        "replay_episode_id": ctx["replay_episode_id"],
        "intervention_id": ctx["intervention_id"],
        "evidence_kind": ctx["evidence_kind"],
        "hash": ctx["cert_hash"],
    }
    
    # Deterministic JSON
    payload_str = json.dumps(payload_to_sign, sort_keys=True, separators=(",", ":"))
    signature_b64 = signer.sign(payload_str.encode("utf-8"))
    
    certificate = RecoveryCertificate(
        id=uuid.uuid4(),
        run_id=uuid.UUID(ctx["run_id"]),
        replay_episode_id=uuid.UUID(ctx["replay_episode_id"]),
        intervention_id=uuid.UUID(ctx["intervention_id"]),
        repair_decision_id=decision_id,
        tenant_id=req.tenant_id,
        certificate_hash=ctx["cert_hash"],
        issued_by="bcrb_automated_pipeline",
        payload_summary="Approved by human",
        is_valid=True,
        evidence_kind=RecoveryEvidenceKind(ctx["evidence_kind"]),
        approval_state="APPROVED",
        cryptographic_signature={
            "algorithm": "Ed25519",
            "public_key": signer.public_key_b64(),
            "signature": signature_b64,
            "signer_id": signer.key_id()
        }
    )
    
    CERTIFICATE_STORE.append(certificate)
    
    await AuditService.log_event(db, req.tenant_id, current_user.id, "RECOVERY_APPROVED", "RecoveryCertificate", str(certificate.id))
    await db.commit()
    
    return certificate

@router.post("/verify")
async def verify_recovery_certificate(payload: dict[str, Any], current_user: User = Depends(require_role(Role.VIEWER))):
    """
    Verifies the cryptographic signature of a recovery certificate.
    """
    from packages.security.src.signer import kms_provider
    from packages.contracts.src.recovery_models import CryptographicSignature
    
    cert_dict = payload.get("certificate", {})
    if not cert_dict:
        raise HTTPException(status_code=400, detail="Certificate payload missing")
        
    signature_dict = cert_dict.get("cryptographic_signature", {})
    if not signature_dict:
        raise HTTPException(status_code=400, detail="Signature missing")
        
    sig = CryptographicSignature(**signature_dict)
    
    # The payload to verify is the exact same one constructed during signing
    payload_to_verify = {
        "run_id": str(cert_dict.get("run_id")),
        "replay_episode_id": str(cert_dict.get("replay_episode_id")),
        "intervention_id": str(cert_dict.get("intervention_id")),
        "evidence_kind": cert_dict.get("evidence_kind"),
        "hash": cert_dict.get("certificate_hash")
    }
    
    is_valid = kms_provider.verify_signature(payload_to_verify, sig)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Signature verification failed")
        
    return {"valid": True}
