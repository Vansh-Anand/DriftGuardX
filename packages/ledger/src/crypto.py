"""
DriftGuard-X v2 — Ledger Cryptography
PRIVATE — All Rights Reserved.

Provides interfaces for Ed25519 signing and verification.
Separates hash integrity (SHA-256) from signer identity (Ed25519).

Includes:
- SignerProtocol: Abstract interface for signing.
- DevelopmentSigner: Local Ed25519 signer using python cryptography.
- KMSProviderSigner: Stub for production hardware/KMS signing.
"""
from __future__ import annotations

import abc
import base64

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


class SignerProtocol(abc.ABC):
    """Abstract interface for Ed25519 signing."""

    @abc.abstractmethod
    def sign(self, payload: bytes) -> str:
        """Sign payload and return base64-encoded signature."""
        ...

    @abc.abstractmethod
    def public_key_b64(self) -> str:
        """Return base64-encoded public key."""
        ...

    @abc.abstractmethod
    def key_id(self) -> str:
        """Return the identity/ID of the key."""
        ...


class DevelopmentSigner(SignerProtocol):
    """
    Local development signer using an ephemeral or provided Ed25519 key.
    DO NOT USE IN PRODUCTION.
    """

    def __init__(self, private_key: ed25519.Ed25519PrivateKey | None = None, key_id: str = "dev-key-01"):
        self._private_key = private_key or ed25519.Ed25519PrivateKey.generate()
        self._public_key = self._private_key.public_key()
        self._key_id = key_id

    def sign(self, payload: bytes) -> str:
        signature = self._private_key.sign(payload)
        return base64.b64encode(signature).decode('utf-8')

    def public_key_b64(self) -> str:
        pub_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        return base64.b64encode(pub_bytes).decode('utf-8')

    def key_id(self) -> str:
        return self._key_id


class KMSProviderSigner(SignerProtocol):
    """
    Stub for production KMS signing.
    In a real environment, this would call AWS KMS, GCP KMS, or HashiCorp Vault.
    """
    def __init__(self, kms_key_arn: str):
        self._kms_key_arn = kms_key_arn

    def sign(self, payload: bytes) -> str:
        raise NotImplementedError("KMS signing requires production credentials.")

    def public_key_b64(self) -> str:
        raise NotImplementedError("KMS public key fetching requires production credentials.")

    def key_id(self) -> str:
        return self._kms_key_arn


from functools import lru_cache


@lru_cache(maxsize=1024)
def verify_signature(public_key_b64: str, payload: bytes, signature_b64: str) -> bool:
    """
    Verify an Ed25519 signature.
    """
    try:
        pub_bytes = base64.b64decode(public_key_b64)
        sig_bytes = base64.b64decode(signature_b64)
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
        public_key.verify(sig_bytes, payload)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False
