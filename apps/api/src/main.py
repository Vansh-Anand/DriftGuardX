"""
DriftGuard-X v2 — FastAPI Application

Structured logging, request IDs, health/readiness endpoints, and full API routing.

PRIVATE — All Rights Reserved.
"""

from __future__ import annotations

import os
import re
import time
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from apps.api.src.config import settings
from apps.api.src.database import create_all_tables
from apps.api.src.middleware import RequestBodyLimitMiddleware
from apps.api.src.observability import setup_observability
from apps.api.src.routers import manifest
from apps.api.src.routes import graph, ingest, runs, telemetry
from apps.api.src.routes.detectors import router as detectors_router
from apps.api.src.routes.jobs import router as jobs_router
from apps.api.src.routes.providers import router as providers_router
from apps.api.src.routes.recovery import router as recovery_router
from apps.api.src.routes.replays import router as replays_router
from apps.api.src.schemas import HealthResponse, ReadinessResponse
from packages.utils.src.version import APP_VERSION

# ─── Logging ──────────────────────────────────────────────────────────────────

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        min_level=os.environ.get("LOG_LEVEL", "INFO")
    ),
)

log = structlog.get_logger()

# ─── App ──────────────────────────────────────────────────────────────────────

APP_ENV = os.environ.get("APP_ENV", settings.environment)

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from starlette.middleware.base import RequestResponseEndpoint


@asynccontextmanager
async def _lifespan(app_: FastAPI) -> AsyncIterator[None]:
    """App lifespan: startup + shutdown."""
    # Setup OpenTelemetry
    setup_observability(app_)

    db_url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./driftguardx_dev.db")
    if "sqlite" in db_url:
        await create_all_tables()
        log.info("startup_complete", db="sqlite_dev", env=APP_ENV)
    else:
        log.info("startup_complete", db="postgres", env=APP_ENV)
    yield
    log.info("shutdown_complete")


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="DriftGuard-X Agentic RAG Reliability Platform API",
    openapi_tags=[
        {"name": "runs", "description": "Execute and manage RAG runs"},
        {"name": "telemetry", "description": "Ingest trace and span data"},
        {"name": "recovery", "description": "Trigger and approve recovery actions"},
        {"name": "manifest", "description": "View cryptographic manifests and replay evidence"}
    ],
    servers=[
        {"url": "http://localhost:8000", "description": "Local environment"}
    ],
    lifespan=_lifespan,
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body, "error_code": "validation_error"},
    )

@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "error_code": "pydantic_validation_error"},
    )

# ─── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Idempotency-Key", "X-Request-ID"],
)
app.add_middleware(RequestBodyLimitMiddleware, max_bytes=settings.max_request_body_bytes)

# ─── Request ID Middleware ─────────────────────────────────────────────────────


_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


@app.middleware("http")
async def add_request_id(request: Request, call_next: RequestResponseEndpoint) -> Response:
    supplied_request_id = request.headers.get("X-Request-ID", "")
    request_id = (
        supplied_request_id
        if _REQUEST_ID_PATTERN.fullmatch(supplied_request_id)
        else str(uuid.uuid4())
    )
    content_length = request.headers.get("Content-Length")
    if content_length:
        try:
            if int(content_length) > settings.max_request_body_bytes:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request body exceeds the configured limit"},
                    headers={"X-Request-ID": request_id},
                )
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid Content-Length header"},
                headers={"X-Request-ID": request_id},
            )
    try:
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=str(request.url.path),
        )
    except AttributeError:
        pass  # older structlog without contextvars
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    response.headers["Cache-Control"] = "no-store"
    if settings.production_like:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    log.info("request_completed", status_code=response.status_code, duration_ms=duration_ms)
    return response


# ─── Health & Readiness ───────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    """Health check — always returns 200 if the process is running."""
    return HealthResponse(
        status="ok",
        version=APP_VERSION,
        timestamp=datetime.now(UTC),
    )


@app.get("/ready", response_model=ReadinessResponse, tags=["system"])
async def readiness(response: Response) -> ReadinessResponse:
    """Readiness probe — checks DB connectivity."""
    checks: dict[str, str] = {}
    try:
        from apps.api.src.database import engine

        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy", fromlist=["text"]).text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
        log.exception("readiness_database_failed")

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    if overall != "ok":
        response.status_code = 503
    return ReadinessResponse(status=overall, checks=checks)


# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(runs.router)
app.include_router(ingest.router)
app.include_router(telemetry.router)
app.include_router(graph.router)
app.include_router(manifest.router)
app.include_router(detectors_router)
app.include_router(replays_router)
if not settings.production_like:
    # The in-process job inspector is a local/test diagnostic surface only.
    # Production async work must use the durable worker queue.
    app.include_router(jobs_router)
app.include_router(providers_router)
app.include_router(recovery_router)


# ─── Exception Handlers ───────────────────────────────────────────────────────


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_exception", exc_type=type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
