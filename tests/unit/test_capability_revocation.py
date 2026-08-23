"""
Unit tests: CapabilityVerifier with revocation store.
Tests HMAC signing, expiry, revocation, and cross-context binding.
"""
import os
import pytest
from datetime import UTC, datetime, timedelta

os.environ.setdefault("DGX_CAPABILITY_SECRET", "test-secret-for-caps")

from packages.memory.src.capabilities import (
    AuthorizationCapability,
    CapabilityRevocationStore,
    CapabilityVerifier,
)


def _future() -> datetime:
    return datetime.now(UTC) + timedelta(hours=1)


def _past() -> datetime:
    return datetime.now(UTC) - timedelta(hours=1)


def _make_cap(**kwargs) -> AuthorizationCapability:
    defaults = {
        "capability_id": "cap-001",
        "requester_id": "agent-alpha",
        "tenant_id": "tenant-xyz",
        "action": "COMPONENT_ROLLBACK",
        "resource": "retriever-v1",
        "expires_at": _future(),
    }
    defaults.update(kwargs)
    return AuthorizationCapability(**defaults)


class TestCapabilityVerifier:
    def setup_method(self):
        CapabilityRevocationStore.reset_for_test()
        self.verifier = CapabilityVerifier(secret_key=b"test-secret-for-caps")

    def test_signed_capability_verifies(self):
        cap = _make_cap()
        signed = self.verifier.sign(cap)
        assert self.verifier.verify(signed)

    def test_unsigned_capability_fails(self):
        cap = _make_cap()
        assert not self.verifier.verify(cap)

    def test_expired_capability_fails(self):
        cap = _make_cap(expires_at=_past())
        signed = self.verifier.sign(cap)
        assert not self.verifier.verify(signed)

    def test_tampered_action_fails(self):
        cap = _make_cap()
        signed = self.verifier.sign(cap)
        signed.action = "DELETE_ALL"  # tamper
        assert not self.verifier.verify(signed)

    def test_tampered_resource_fails(self):
        cap = _make_cap()
        signed = self.verifier.sign(cap)
        signed.resource = "prod-database"  # tamper
        assert not self.verifier.verify(signed)

    def test_revoked_capability_fails(self):
        cap = _make_cap()
        signed = self.verifier.sign(cap)
        assert self.verifier.verify(signed)  # passes before revocation
        self.verifier.revoke(signed.capability_id)
        assert not self.verifier.verify(signed)  # fails after revocation

    def test_different_capabilities_same_action_are_independent(self):
        cap1 = _make_cap(capability_id="cap-A", requester_id="agent-1")
        cap2 = _make_cap(capability_id="cap-B", requester_id="agent-2")
        s1 = self.verifier.sign(cap1)
        s2 = self.verifier.sign(cap2)
        self.verifier.revoke("cap-A")
        assert not self.verifier.verify(s1)
        assert self.verifier.verify(s2), "Revoking cap-A must not affect cap-B"

    def test_cross_requester_token_fails(self):
        """Capability signed for agent-1 must not verify as agent-2."""
        cap_orig = _make_cap(requester_id="agent-1", capability_id="cap-X")
        signed = self.verifier.sign(cap_orig)
        # Forge a capability with the same ID but different requester
        forged = AuthorizationCapability(
            capability_id="cap-X",
            requester_id="agent-EVIL",
            tenant_id="tenant-xyz",
            action="COMPONENT_ROLLBACK",
            resource="retriever-v1",
            expires_at=_future(),
            signature=signed.signature,  # reuse original signature
        )
        assert not self.verifier.verify(forged)


class TestRevocationStore:
    def setup_method(self):
        CapabilityRevocationStore.reset_for_test()

    def test_revocation_is_persistent_within_process(self):
        store = CapabilityRevocationStore.get_instance()
        store.revoke("cap-123")
        store2 = CapabilityRevocationStore.get_instance()
        assert store2.is_revoked("cap-123")

    def test_revocation_count_tracks(self):
        store = CapabilityRevocationStore.get_instance()
        store.revoke("x")
        store.revoke("y")
        assert store.revoked_count() == 2

    def test_non_revoked_id_returns_false(self):
        store = CapabilityRevocationStore.get_instance()
        assert not store.is_revoked("never-revoked")
