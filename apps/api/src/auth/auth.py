"""
DriftGuard-X v2 — OIDC & Mock Authentication
PRIVATE — All Rights Reserved.

Provides OIDC JWKS token validation for production and mock tokens for local testing.
"""
import json
import urllib.request
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from apps.api.src.config import settings
from packages.contracts.src.auth import Role, Tenant, User

# ─── Mock Identity ─────────────────────────────────────────────────────────────
MOCK_USER_ID = UUID("00000000-0000-0000-0000-000000000000")
MOCK_TENANT_ID = UUID("00000000-0000-0000-FFFF-000000000001")

MOCK_TENANT = Tenant(id=MOCK_TENANT_ID, name="Acme Corp")
MOCK_USER = User(id=MOCK_USER_ID, tenant_id=MOCK_TENANT_ID, email="admin@acme.com", roles=[Role.ADMIN])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# JWKS Cache
_JWKS_CLIENT = None

def get_jwks() -> dict[str, Any]:
    global _JWKS_CLIENT
    if not _JWKS_CLIENT and settings.oidc_jwks_uri:
        with urllib.request.urlopen(settings.oidc_jwks_uri) as response:
            _JWKS_CLIENT = json.loads(response.read().decode("utf-8"))
    return _JWKS_CLIENT


def verify_token(token: str) -> dict:
    """Verifies and decodes a JWT."""
    if settings.auth_mode == "mock":
        # Accept the mock token literally
        if token == "mock-admin-token":
            return {"sub": str(MOCK_USER_ID), "email": MOCK_USER.email, "roles": ["ADMIN"]}

        # Or decode assuming mock secret if provided
        try:
            payload = jwt.decode(token, "mock_secret_key_for_development", algorithms=["HS256"])
            return payload
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate mock credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # OIDC Mode
    try:
        jwks = get_jwks()
        unverified_header = jwt.get_unverified_header(token)

        rsa_key = {}
        for key in jwks.get("keys", []):
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }
                break

        if rsa_key:
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=["RS256"],
                audience=settings.oidc_audience,
                issuer=settings.oidc_issuer
            )
            return payload

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to find appropriate key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {e!s}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (ValueError, RuntimeError, KeyError, TypeError, OSError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )
