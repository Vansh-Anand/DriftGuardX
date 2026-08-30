"""
DriftGuard-X v2 — Replay Routes

GET /v1/replays/{id} — get replay metrics and provenance
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.database import get_db
from apps.api.src.dependencies import get_current_tenant
from apps.api.src.models import ReplayEpisodeORM
from apps.api.src.schemas import ReplayResponse
from packages.contracts.src.auth import Tenant

router = APIRouter(prefix="/v1", tags=["replays"])


@router.get("/replays/{replay_id}", response_model=ReplayResponse)
async def get_replay(
    replay_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
) -> ReplayResponse:
    """Get replay metrics and provenance."""
    # Need to join with manifest to get manifest_hash
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(ReplayEpisodeORM)
        .options(selectinload(ReplayEpisodeORM.manifest))
        .where(ReplayEpisodeORM.id == replay_id, ReplayEpisodeORM.tenant_id == tenant.id)
    )
    episode = result.scalar_one_or_none()
    if episode is None:
        raise HTTPException(status_code=404, detail=f"Replay {replay_id} not found")

    manifest_hash = episode.manifest.manifest_hash if episode.manifest else None

    return ReplayResponse(
        id=episode.id,
        original_run_id=episode.original_run_id,
        status=episode.status,
        swapped_component_type=episode.swapped_component_type,
        original_version_tag=episode.original_version_tag,
        replay_version_tag=episode.replay_version_tag,
        original_reliability_score=episode.original_reliability_score,
        replay_reliability_score=episode.replay_reliability_score,
        reliability_improvement=episode.reliability_improvement,
        original_reliability_vector=episode.original_reliability_vector,
        replay_reliability_vector=episode.replay_reliability_vector,
        reliability_delta=episode.reliability_delta,
        created_at=episode.created_at,
        completed_at=episode.completed_at,
        is_synthetic=episode.is_synthetic,
        evidence_kind=("synthetic_simulation" if episode.is_synthetic else "controlled_replay"),
        manifest_id=episode.manifest_id,
        manifest_hash=manifest_hash,
        is_pinned=episode.is_pinned,
    )
