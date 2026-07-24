"""
DriftGuard-X v2 — Providers API
PRIVATE — All Rights Reserved.

Exposes model provider health, cost, and availability.
"""
from fastapi import APIRouter, Depends
from packages.provider_registry.src.registry import ProviderRegistry
from apps.api.src.dependencies import get_current_user

router = APIRouter(prefix="/v1/providers", tags=["providers"])

@router.get("/")
async def list_providers(user = Depends(get_current_user)):
    """List available LLM providers, health status, and pricing."""
    return ProviderRegistry.list_providers()
