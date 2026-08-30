"""
DriftGuard-X v2 — Graph API Routes
PRIVATE — All Rights Reserved.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.database import get_db
from apps.api.src.dependencies import get_current_tenant
from apps.api.src.models_graph import CausalGraphORM, GraphEdgeORM
from packages.contracts.src.auth import Tenant
from packages.contracts.src.graph import CausalGraph

router = APIRouter(prefix="/v1/graph", tags=["Graph"])


@router.get("/snapshot/{run_id}", response_model=CausalGraph)
async def get_graph_snapshot(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
) -> CausalGraph:
    """Retrieve a full graph snapshot by run ID."""
    stmt = select(CausalGraphORM).where(
        CausalGraphORM.tenant_id == str(tenant.id), CausalGraphORM.run_id == str(run_id)
    )
    result = await db.execute(stmt)
    snapshot = result.scalar_one_or_none()

    if not snapshot:
        raise HTTPException(status_code=404, detail="Graph not found")

    return CausalGraph.model_validate(
        {
            "tenant_id": snapshot.tenant_id,
            "run_id": snapshot.run_id,
            "nodes": snapshot.nodes_json,
            "edges": snapshot.edges_json,
            "builder_version": snapshot.builder_version,
            "trace_digest": snapshot.trace_digest,
            "graph_hash": snapshot.graph_hash,
            "created_at": snapshot.created_at,
        }
    )


@router.get("/query/descendants/{node_id}")
async def get_descendants(
    node_id: str,
    depth: int = 5,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
) -> dict[str, object]:
    """
    Find all descendants of a specific node across all graphs.
    Useful for finding symptoms of a changed component version.
    """
    # Direct descendants only for now. Do not imply recursive depth support.
    if depth != 1:
        raise HTTPException(status_code=400, detail="Only depth=1 is currently supported")
    stmt = (
        select(GraphEdgeORM)
        .join(CausalGraphORM, GraphEdgeORM.graph_hash == CausalGraphORM.graph_hash)
        .where(
            GraphEdgeORM.source_id == node_id,
            CausalGraphORM.tenant_id == str(tenant.id),
        )
        .limit(100)
    )

    result = await db.execute(stmt)
    edges = result.scalars().all()

    return {
        "node_id": node_id,
        "descendants": [
            {
                "target_id": edge.target_id,
                "edge_type": edge.edge_type,
                "graph_hash": edge.graph_hash,
            }
            for edge in edges
        ],
    }
