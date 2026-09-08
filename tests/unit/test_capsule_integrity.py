from datetime import timedelta

import pytest

from packages.recovery.src.capsule import CompatibilityConstraint, RollbackCapsule


@pytest.mark.parametrize(
    "field,value",
    [
        ("target_state", {"version": "substituted"}),
        ("artifact_hashes", {"config": "substituted"}),
        ("compatibility_constraints", []),
        ("verify_steps", []),
        ("created_by", "another-actor"),
    ],
)
def test_execution_conditions_are_sealed(field, value):
    capsule = RollbackCapsule(
        target_state={"version": "v2"},
        artifact_hashes={"config": "original"},
        compatibility_constraints=[CompatibilityConstraint("retriever", "v2", "must match")],
        verify_steps=["health"],
    )
    assert capsule.is_usable()[0]
    setattr(capsule, field, value)
    assert not capsule.verify_integrity()
    assert not capsule.is_usable()[0]


def test_expiry_extension_is_tampering():
    capsule = RollbackCapsule()
    capsule.expires_at += timedelta(days=30)
    assert not capsule.is_usable()[0]


def test_nested_constraint_mutation_is_tampering():
    capsule = RollbackCapsule(
        compatibility_constraints=[CompatibilityConstraint("retriever", "v2", "must match")],
    )
    capsule.compatibility_constraints[0].expected_version_id = "v3"
    assert not capsule.is_usable()[0]


def test_consuming_capsule_preserves_seal_but_blocks_reuse():
    capsule = RollbackCapsule()
    capsule.seal_used()
    assert capsule.verify_integrity()
    assert not capsule.is_usable()[0]
