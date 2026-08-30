import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.database import get_db
from apps.api.src.dependencies import get_current_tenant
from apps.api.src.models_ingestion import CorpusVersionORM
from apps.api.src.models_manifest import ManifestORM
from packages.contracts.src.models import ReplayStateManifest
from packages.rag_pipeline.src.adapters.manifest_store import ManifestStore

router = APIRouter(prefix="/manifests", tags=["Manifests"])


class VerificationResponse(BaseModel):
    is_valid: bool
    missing_dependencies: list[str]
    message: str


@router.get("/{manifest_id}")
async def get_manifest(
    manifest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant=Depends(get_current_tenant),
):
    result = await db.execute(
        select(ManifestORM).where(ManifestORM.id == manifest_id, ManifestORM.tenant_id == tenant.id)
    )
    orm_manifest = result.scalar_one_or_none()
    if not orm_manifest:
        raise HTTPException(status_code=404, detail="Manifest not found")

    store = ManifestStore()
    try:
        manifest_json = store.get_manifest(orm_manifest.manifest_hash)
        return {"manifest_hash": orm_manifest.manifest_hash, "payload": manifest_json}
    except (ValueError, RuntimeError, KeyError, TypeError, OSError):
        # Fallback to postgres payload if minio fails
        return {"manifest_hash": orm_manifest.manifest_hash, "payload": orm_manifest.payload}


@router.get("/{manifest_id}/verify", response_model=VerificationResponse)
async def verify_manifest(
    manifest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant=Depends(get_current_tenant),
):
    result = await db.execute(
        select(ManifestORM).where(ManifestORM.id == manifest_id, ManifestORM.tenant_id == tenant.id)
    )
    orm_manifest = result.scalar_one_or_none()
    if not orm_manifest:
        raise HTTPException(status_code=404, detail="Manifest not found")

    missing_deps = []

    # Reconstruct the Pydantic model to use its logic
    manifest = ReplayStateManifest(**orm_manifest.payload)

    # Check if fully pinned
    if not manifest.is_fully_pinned():
        missing_deps.append("manifest_not_fully_pinned")

    # Check corpus dependency
    if manifest.corpus_version_id:
        corpus_res = await db.execute(
            select(CorpusVersionORM).filter_by(version_tag=manifest.corpus_version_id)
        )
        if not corpus_res.scalar_one_or_none():
            missing_deps.append(f"corpus_version_missing: {manifest.corpus_version_id}")

    # Hash check
    computed_hash = manifest.compute_hash()
    if computed_hash != manifest.manifest_hash:
        missing_deps.append(
            f"hash_mismatch: computed {computed_hash} != stored {manifest.manifest_hash}"
        )

    is_valid = len(missing_deps) == 0
    message = (
        "Manifest dependencies verified."
        if is_valid
        else "Manifest dependencies failed verification."
    )

    return VerificationResponse(
        is_valid=is_valid, missing_dependencies=missing_deps, message=message
    )
