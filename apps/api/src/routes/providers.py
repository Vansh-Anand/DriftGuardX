"""
DriftGuard-X v2 — Providers API
PRIVATE — All Rights Reserved.

Exposes model provider health, cost, and availability.
"""

from typing import Any

from fastapi import APIRouter, Depends

from apps.api.src.dependencies import get_current_tenant
from packages.contracts.src.auth import Tenant
from packages.provider_registry.src.registry import ProviderRegistry

router = APIRouter(prefix="/v1/providers", tags=["providers"])


@router.get("/")
async def list_providers(
    tenant: Tenant = Depends(get_current_tenant),
) -> dict[str, Any]:
    """List available LLM providers, health status, and pricing."""
    return ProviderRegistry.list_providers()
