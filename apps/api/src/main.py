"""
DriftGuard-X v2 — FastAPI Application

Structured logging, request IDs, health/readiness endpoints, and full API routing.

PRIVATE — All Rights Reserved.
"""
from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.src.database import create_all_tables
from apps.api.src.routes import ingest, runs, telemetry, graph
from apps.api.src.routers import manifest
from apps.api.src.routes.detectors import router as detectors_router
from apps.api.src.routes.replays import router as replays_router
from apps.api.src.routes.runs import router as runs_router
from apps.api.src.routes.jobs import router as jobs_router
from apps.api.src.routes.providers import router as providers_router
from apps.api.src.schemas import HealthResponse, ReadinessResponse

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

APP_VERSION = os.environ.get("APP_VERSION", "0.1.0")
APP_ENV = os.environ.get("APP_ENV", "development")

from contextlib import asynccontextmanager


@asynccontextmanager
async def _lifespan(app_: "FastAPI"):
    """App lifespan: startup + shutdown."""
    db_url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./driftguardx_dev.db")
    if "sqlite" in db_url:
        await create_all_tables()
        log.info("startup_complete", db="sqlite_dev", env=APP_ENV)
    else:
        log.info("startup_complete", db="postgres", env=APP_ENV)
    yield
    log.info("shutdown_complete")


app = FastAPI(
    title="DriftGuard-X v2 API",
    description=(
        "Agentic RAG Reliability Platform — Versioned tracing, causal reliability graph, "
        "deterministic replay, and policy-gated recovery.\n\n"
        "⚠️ DEMO/SYNTHETIC: All runs in development mode use deterministic mock data."
    ),
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=_lifespan,
)

# ─── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Request ID Middleware ─────────────────────────────────────────────────────

@app.middleware("http")
async def add_request_id(request: Request, call_next: Callable) -> Response:
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
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
    log.info("request_completed", status_code=response.status_code, duration_ms=duration_ms)
    return response

# ─── Health & Readiness ───────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    """Health check — always returns 200 if the process is running."""
    return HealthResponse(
        status="ok",
        version=APP_VERSION,
        timestamp=datetime.now(timezone.utc),
    )


@app.get("/ready", response_model=ReadinessResponse, tags=["system"])
async def readiness() -> ReadinessResponse:
    """Readiness probe — checks DB connectivity."""
    checks: dict[str, str] = {}
    try:
        from apps.api.src.database import engine
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy", fromlist=["text"]).text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return ReadinessResponse(status=overall, checks=checks)


# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(runs.router)
app.include_router(ingest.router)
app.include_router(telemetry.router)
app.include_router(graph.router)
app.include_router(manifest.router)
app.include_router(detectors_router)
app.include_router(replays_router)
app.include_router(jobs_router)
app.include_router(providers_router)


# ─── Exception Handlers ───────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled_exception", exc_type=type(exc).__name__, exc_str=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error_type": type(exc).__name__},
    )
