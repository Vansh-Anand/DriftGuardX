"""Fail closed when a new private API route omits derived tenant scoping."""

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from apps.api.src.dependencies import get_current_tenant
from apps.api.src.main import app

PUBLIC_PATHS = {"/health", "/ready", "/openapi.json", "/docs", "/redoc"}


def _contains_tenant_dependency(dependant: Dependant) -> bool:
    if dependant.call is get_current_tenant:
        return True
    return any(_contains_tenant_dependency(child) for child in dependant.dependencies)


def test_every_private_api_route_derives_tenant_scope() -> None:
    missing: list[str] = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or route.path in PUBLIC_PATHS:
            continue
        if not _contains_tenant_dependency(route.dependant):
            methods = ",".join(sorted(route.methods or []))
            missing.append(f"{methods} {route.path}")

    assert missing == [], "Private routes without derived tenant scope: " + "; ".join(missing)
