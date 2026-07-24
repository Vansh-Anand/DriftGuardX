"""
DriftGuard-X v2 — Mock OIDC Authentication
PRIVATE — All Rights Reserved.

Provides development-mode login, JWT verification, and scoped API tokens.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from packages.contracts.src.auth import User, Role, Tenant

# ─── Mock Secrets & Configuration ──────────────────────────────────────────────
SECRET_KEY = "mock_secret_key_for_development"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Mock static database for identities
MOCK_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
MOCK_USER_ID = UUID("11111111-1111-1111-1111-111111111111")

MOCK_TENANT = Tenant(id=MOCK_TENANT_ID, name="Acme Corp")
MOCK_USER = User(id=MOCK_USER_ID, tenant_id=MOCK_TENANT_ID, email="admin@acme.com", roles=[Role.ADMIN])


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a signed JWT."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """Verifies and decodes a JWT."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
