"""
DriftGuard-X v2 — OIDC & Mock Authentication
PRIVATE — All Rights Reserved.

Provides OIDC JWKS token validation for production and mock tokens for local testing.
"""

import asyncio
import time
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx
import jwt
from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from apps.api.src.config import settings
from packages.contracts.src.auth import Role, Tenant, User

# ─── Mock Identity ─────────────────────────────────────────────────────────────
MOCK_USER_ID = UUID("00000000-0000-0000-0000-000000000000")
MOCK_TENANT_ID = UUID("00000000-0000-0000-FFFF-000000000001")
MOCK_JWT_SECRET = "driftguardx-local-mock-key-32-bytes-minimum"

MOCK_TENANT = Tenant(id=MOCK_TENANT_ID, name="Acme Corp")
MOCK_USER = User(
    id=MOCK_USER_ID, tenant_id=MOCK_TENANT_ID, email="admin@acme.com", roles=[Role.ADMIN]
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# JWKS Cache
_JWKS_CLIENT: dict[str, Any] | None = None
_JWKS_EXPIRES_AT = 0.0
_JWKS_LOCK = asyncio.Lock()
_JWKS_TTL_SECONDS = 300.0


async def get_jwks(*, force_refresh: bool = False) -> dict[str, Any]:
    """Fetch and briefly cache the configured JWKS with bounded network I/O."""
    global _JWKS_CLIENT, _JWKS_EXPIRES_AT
    uri = settings.oidc_jwks_uri
    if not uri:
        raise ValueError("OIDC JWKS URI is not configured")
    parsed = urlparse(uri)
    if settings.environment in {"staging", "prod"} and parsed.scheme != "https":
        raise ValueError("OIDC JWKS URI must use HTTPS outside local/test environments")

    now = time.monotonic()
    if not force_refresh and _JWKS_CLIENT is not None and now < _JWKS_EXPIRES_AT:
        return _JWKS_CLIENT

    async with _JWKS_LOCK:
        now = time.monotonic()
        if not force_refresh and _JWKS_CLIENT is not None and now < _JWKS_EXPIRES_AT:
            return _JWKS_CLIENT
        timeout = httpx.Timeout(5.0, connect=3.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            response = await client.get(uri, headers={"Accept": "application/json"})
            response.raise_for_status()
            if len(response.content) > 1024 * 1024:
                raise ValueError("OIDC JWKS response exceeds the 1 MiB limit")
            payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("keys"), list):
            raise ValueError("OIDC JWKS response is malformed")
        _JWKS_CLIENT = payload
        _JWKS_EXPIRES_AT = time.monotonic() + _JWKS_TTL_SECONDS
        return payload


async def verify_token(token: str) -> dict[str, Any]:
    """Verifies and decodes a JWT."""
    if settings.auth_mode == "mock":
        # Accept the mock token literally
        if token == "mock-admin-token":
            return {"sub": str(MOCK_USER_ID), "email": MOCK_USER.email, "roles": ["ADMIN"]}

        # Or decode assuming mock secret if provided
        try:
            payload = jwt.decode(token, MOCK_JWT_SECRET, algorithms=["HS256"])
            return payload
        except jwt.PyJWTError:
            import structlog
            structlog.get_logger().error("auth_failure", reason="invalid_mock")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate mock credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # OIDC Mode
    try:
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        if not kid:
            raise jwt.PyJWTError("Token header missing kid")

        jwks = await get_jwks()

        def find_key(keys: list[dict[str, Any]]) -> dict[str, Any]:
            return next((key for key in keys if key.get("kid") == kid), {})

        rsa_key = find_key(jwks["keys"])
        if not rsa_key:
            # Key rotation: refresh once before rejecting the token.
            jwks = await get_jwks(force_refresh=True)
            rsa_key = find_key(jwks["keys"])

        if rsa_key:
            verification_key = jwt.PyJWK.from_dict(rsa_key).key
            payload = jwt.decode(
                token,
                verification_key,
                algorithms=["RS256"],
                audience=settings.oidc_audience,
                issuer=settings.oidc_issuer,
                options={"require": ["exp", "iat", "sub"]},
            )
            return payload

        import structlog
        structlog.get_logger().error("auth_failure", reason="key_not_found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to find appropriate key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {e!s}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (httpx.HTTPError, ValueError, RuntimeError, KeyError, TypeError, OSError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )
