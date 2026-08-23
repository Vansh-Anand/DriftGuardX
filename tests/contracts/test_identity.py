"""
Tests for packages/contracts/src/identity.py

Covers:
- ComponentIdentity construction and validation
- identity_hash determinism
- artifact_hash format validation
- Cross-tenant rejection
- Malformed component metadata
- identity_hash sensitivity to each field
"""
from __future__ import annotations

import hashlib
from uuid import uuid4

import pytest

from packages.contracts.src.identity import ComponentIdentity
from packages.contracts.src.models import ComponentType


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def valid_hash() -> str:
    return hashlib.sha256(b"test").hexdigest()


def make_identity(**overrides) -> ComponentIdentity:
    defaults = dict(
        component_id="retriever-shard-01",
        component_type=ComponentType.RETRIEVER,
        version="v1.2.3",
        artifact_hash=valid_hash(),
        tenant_id=uuid4(),
    )
    defaults.update(overrides)
    return ComponentIdentity(**defaults)


# ─── ComponentIdentity Construction ──────────────────────────────────────────

class TestComponentIdentityConstruction:
    def test_valid_construction(self):
        identity = make_identity()
        assert identity.component_id == "retriever-shard-01"
        assert identity.component_type == ComponentType.RETRIEVER

    def test_optional_version_none(self):
        identity = make_identity(version=None)
        assert identity.version is None

    def test_optional_artifact_hash_none(self):
        identity = make_identity(artifact_hash=None)
        assert identity.artifact_hash is None

    def test_new_component_types_accepted(self):
        """Extended component types added in this pass must be usable."""
        for ct in [ComponentType.MODEL, ComponentType.PROMPT,
                   ComponentType.EMBEDDING_MODEL, ComponentType.INDEX,
                   ComponentType.PLANNER, ComponentType.SCHEMA,
                   ComponentType.CONFIGURATION, ComponentType.EXTERNAL_SERVICE,
                   ComponentType.OTHER]:
            identity = make_identity(component_type=ct)
            assert identity.component_type == ct


# ─── Artifact Hash Validation ─────────────────────────────────────────────────

class TestArtifactHashValidation:
    def test_valid_sha256_accepted(self):
        identity = make_identity(artifact_hash=valid_hash())
        assert len(identity.artifact_hash) == 64

    def test_short_hash_rejected(self):
        with pytest.raises(Exception):
            make_identity(artifact_hash="abc123")

    def test_non_hex_hash_rejected(self):
        with pytest.raises(Exception):
            make_identity(artifact_hash="g" * 64)  # 'g' is not hex

    def test_hash_is_lowercased(self):
        upper_hash = valid_hash().upper()
        identity = make_identity(artifact_hash=upper_hash)
        assert identity.artifact_hash == upper_hash.lower()


# ─── identity_hash ────────────────────────────────────────────────────────────

class TestIdentityHash:
    def test_returns_64_hex(self):
        identity = make_identity()
        h = identity.identity_hash()
        assert len(h) == 64
        int(h, 16)

    def test_deterministic(self):
        tenant_id = uuid4()
        i1 = make_identity(tenant_id=tenant_id)
        i2 = make_identity(tenant_id=tenant_id)
        assert i1.identity_hash() == i2.identity_hash()

    def test_different_component_id_different_hash(self):
        tenant_id = uuid4()
        i1 = make_identity(component_id="shard-01", tenant_id=tenant_id)
        i2 = make_identity(component_id="shard-02", tenant_id=tenant_id)
        assert i1.identity_hash() != i2.identity_hash()

    def test_different_tenant_different_hash(self):
        i1 = make_identity(tenant_id=uuid4())
        i2 = make_identity(tenant_id=uuid4())
        assert i1.identity_hash() != i2.identity_hash()

    def test_different_version_different_hash(self):
        tenant_id = uuid4()
        i1 = make_identity(version="v1", tenant_id=tenant_id)
        i2 = make_identity(version="v2", tenant_id=tenant_id)
        assert i1.identity_hash() != i2.identity_hash()

    def test_different_component_type_different_hash(self):
        tenant_id = uuid4()
        i1 = make_identity(component_type=ComponentType.RETRIEVER, tenant_id=tenant_id)
        i2 = make_identity(component_type=ComponentType.MODEL, tenant_id=tenant_id)
        assert i1.identity_hash() != i2.identity_hash()


# ─── Cross-Tenant Rejection ───────────────────────────────────────────────────

class TestCrossTenantRejection:
    def test_same_tenant_passes(self):
        tenant_id = uuid4()
        identity = make_identity(tenant_id=tenant_id)
        identity.cross_tenant_check(tenant_id)  # must not raise

    def test_different_tenant_raises(self):
        identity = make_identity(tenant_id=uuid4())
        with pytest.raises(ValueError, match="Cross-tenant access rejected"):
            identity.cross_tenant_check(uuid4())

    def test_is_same_tenant_true(self):
        tenant_id = uuid4()
        i1 = make_identity(tenant_id=tenant_id)
        i2 = make_identity(tenant_id=tenant_id, component_id="other")
        assert i1.is_same_tenant(i2) is True

    def test_is_same_tenant_false(self):
        i1 = make_identity(tenant_id=uuid4())
        i2 = make_identity(tenant_id=uuid4())
        assert i1.is_same_tenant(i2) is False


# ─── Malformed Component Metadata ────────────────────────────────────────────

class TestMalformedComponentMetadata:
    def test_empty_component_id_rejected(self):
        with pytest.raises(Exception):
            make_identity(component_id="")

    def test_version_empty_string_rejected(self):
        with pytest.raises(Exception):
            make_identity(version="")  # min_length=1 when set
