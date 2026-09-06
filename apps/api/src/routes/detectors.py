"""
DriftGuard-X v2 — GAT Detector API Routes
Allows online trace evaluation and run-level anomaly detection via the trained GAT model.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from apps.api.src.database import get_db
from apps.api.src.dependencies import get_current_tenant
from apps.api.src.models import SpanRecordORM

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

try:
    from packages.detectors.src.gat_inference import GATTraceDetector
except ModuleNotFoundError as exc:
    if exc.name not in {"torch", "torch_geometric"}:
        raise
    GATTraceDetector = None  # type: ignore[assignment,misc]
    _GAT_UNAVAILABLE_REASON = "Install the project with the ml extra to enable GAT detection."
else:
    _GAT_UNAVAILABLE_REASON = None

router = APIRouter(prefix="/v1/detectors", tags=["detectors"])

# Singleton detector instance
_MODEL_PATH = os.environ.get(
    "GAT_MODEL_PATH",
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../../driftguardx_gat_model.pth")
    ),
)
detector = GATTraceDetector(model_path=_MODEL_PATH) if GATTraceDetector is not None else None


def _require_detector() -> Any:
    if detector is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_GAT_UNAVAILABLE_REASON,
        )
    return detector


# ─── Pydantic Schemas ─────────────────────────────────────────────────────────


class SpanInput(BaseModel):
    span_id: str
    parent_id: str | None = None
    duration_ms: float = 0.0
    operation_name: str = "unknown"
    is_error: bool = False


class TraceEvaluateRequest(BaseModel):
    trace_id: str | None = None
    spans: list[SpanInput] = Field(..., min_length=1)


class RootCauseCandidate(BaseModel):
    span_id: str
    operation_name: str
    duration_ms: float
    is_error: bool
    self_time_ratio: float


class TraceEvaluateResponse(BaseModel):
    is_fault: bool
    fault_probability: float
    predicted_class: int
    num_spans: int
    root_cause_candidates: list[RootCauseCandidate]


class RunEvaluateResponse(BaseModel):
    run_id: str
    is_fault: bool
    fault_probability: float
    predicted_class: int
    num_spans: int
    root_cause_candidates: list[RootCauseCandidate]


# ─── Endpoints ───────────────────────────────────────────────────────────────


@router.get("/gat/status")
async def get_gat_status(tenant=Depends(get_current_tenant)) -> dict[str, Any]:
    """Check if the GAT model is loaded and ready for inference."""
    if detector is None:
        return {
            "model_loaded": False,
            "device": None,
            "model_architecture": "DriftGuardX_GAT (optional ml extra)",
            "unavailable_reason": _GAT_UNAVAILABLE_REASON,
        }
    return {
        "model_loaded": detector.is_loaded,
        "device": str(detector.device),
        "model_architecture": "DriftGuardX_GAT (3-layer GAT with dual mean+max pooling)",
    }


@router.post("/gat/trace", response_model=TraceEvaluateResponse)
async def evaluate_trace(
    request: TraceEvaluateRequest,
    tenant=Depends(get_current_tenant),
) -> TraceEvaluateResponse:
    """Evaluate an arbitrary list of spans using the trained GAT model."""
    raw_spans = [s.model_dump() for s in request.spans]
    result = _require_detector().detect_trace_anomaly(raw_spans)

    candidates = [
        RootCauseCandidate(
            span_id=c["span_id"],
            operation_name=c["operation_name"],
            duration_ms=c["duration_ms"],
            is_error=c["is_error"],
            self_time_ratio=c["self_time_ratio"],
        )
        for c in result.get("root_cause_candidates", [])
    ]

    return TraceEvaluateResponse(
        is_fault=result["is_fault"],
        fault_probability=result["fault_probability"],
        predicted_class=result["predicted_class"],
        num_spans=result["num_spans"],
        root_cause_candidates=candidates,
    )


@router.post("/gat/evaluate-run/{run_id}", response_model=RunEvaluateResponse)
async def evaluate_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant=Depends(get_current_tenant),
) -> RunEvaluateResponse:
    """
    Fetch all ingested spans for a specific run_id and evaluate with GAT.
    """
    stmt = (
        select(SpanRecordORM)
        .where(
            SpanRecordORM.run_id == run_id,
            SpanRecordORM.tenant_id == tenant.id,
        )
        .order_by(SpanRecordORM.start_time.asc())
    )
    res = await db.execute(stmt)
    span_records = res.scalars().all()

    if not span_records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"No spans found for run_id {run_id}"
        )

    spans = []
    for s in span_records:
        dur_ms = 0.0
        if s.start_time and s.end_time:
            dur_ms = max(0.0, (s.end_time - s.start_time).total_seconds() * 1000.0)

        is_err = s.status_code == "ERROR"
        spans.append(
            {
                "span_id": s.span_id,
                "parent_id": s.parent_span_id,
                "duration_ms": dur_ms,
                "operation_name": s.name or "unknown",
                "is_error": is_err,
            }
        )

    result = _require_detector().detect_trace_anomaly(spans)

    candidates = [
        RootCauseCandidate(
            span_id=c["span_id"],
            operation_name=c["operation_name"],
            duration_ms=c["duration_ms"],
            is_error=c["is_error"],
            self_time_ratio=c["self_time_ratio"],
        )
        for c in result.get("root_cause_candidates", [])
    ]

    return RunEvaluateResponse(
        run_id=str(run_id),
        is_fault=result["is_fault"],
        fault_probability=result["fault_probability"],
        predicted_class=result["predicted_class"],
        num_spans=result["num_spans"],
        root_cause_candidates=candidates,
    )
